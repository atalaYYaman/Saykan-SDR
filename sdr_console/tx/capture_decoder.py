"""RX yakalamasından OOK darbe analizi ve (kaba) bit çözümü."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

RollingCodeStatus = Literal["stable", "probably_rolling", "insufficient_data"]


@dataclass(frozen=True, slots=True)
class PulseEvent:
    """Tek bir yüksek veya düşük zarf dilimi."""

    start_s: float
    end_s: float
    duration_s: float
    level: bool  # True = eşik üstü (ON), False = eşik altı (OFF)


@dataclass(frozen=True, slots=True)
class OokCapture:
    """Bir yakalamanın darbe zamanlaması ve isteğe bağlı çözülen bitler."""

    pulses: tuple[PulseEvent, ...]
    bits: tuple[int, ...] | None
    sample_rate_hz: float
    threshold: float


@dataclass(frozen=True, slots=True)
class RollingCodeAssessment:
    """Birden fazla yakalama karşılaştırmasının sonucu."""

    status: RollingCodeStatus
    message: str
    capture_count: int
    matching_pairs: int
    differing_pairs: int


def envelope_detect(iq: np.ndarray) -> np.ndarray:
    """IQ bloğundan genlik zarfını çıkar (`|iq|`)."""
    arr = np.asarray(iq)
    if arr.ndim != 1:
        arr = arr.reshape(-1)
    return np.abs(arr)


def threshold_to_bits(
    envelope: np.ndarray,
    threshold: float,
    sample_rate: float,
) -> list[PulseEvent]:
    """Zarfı eşikle; ON/OFF dilimlerinin zamanlarını çıkar."""
    arr = np.asarray(envelope)
    if arr.ndim != 1:
        arr = arr.reshape(-1)
    if arr.size == 0:
        return []
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")

    above = arr >= float(threshold)
    pulses: list[PulseEvent] = []
    start_idx = 0
    current_level = bool(above[0])

    for idx in range(1, arr.size):
        level = bool(above[idx])
        if level != current_level:
            pulses.append(_segment_to_pulse(start_idx, idx, sample_rate, current_level))
            start_idx = idx
            current_level = level

    pulses.append(_segment_to_pulse(start_idx, arr.size, sample_rate, current_level))
    return pulses


def decode_ook_pulses(pulses: list[PulseEvent]) -> list[int] | None:
    """Darbe sürelerinden bit dizisini çıkarmayı dene.

    Önce PT2262 benzeri (yüksek+düşük çifti) kodlamayı, sonra tek ON
    darbe genişliği kodlamasını dener. Kesin çözüm yoksa ``None``.
    """
    if not pulses:
        return None

    pair_bits = _decode_high_low_pairs(pulses)
    if pair_bits is not None:
        return pair_bits

    return _decode_on_pulse_widths(pulses)


def analyze_capture(
    iq: np.ndarray,
    sample_rate_hz: float,
    threshold: float | None = None,
) -> OokCapture:
    """Ham IQ'dan tam analiz zinciri: zarf → darbeler → (isteğe bağlı) bitler."""
    envelope = envelope_detect(iq)
    if envelope.size == 0:
        raise ValueError("iq must contain at least one sample")
    if sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be positive")

    if threshold is None:
        peak = float(np.max(envelope))
        floor = float(np.min(envelope))
        threshold = (peak + floor) * 0.5

    pulses = threshold_to_bits(envelope, threshold, sample_rate_hz)
    decoded = decode_ook_pulses(pulses)
    bits = tuple(decoded) if decoded is not None else None
    return OokCapture(
        pulses=tuple(pulses),
        bits=bits,
        sample_rate_hz=float(sample_rate_hz),
        threshold=float(threshold),
    )


def captures_equivalent(
    left: OokCapture,
    right: OokCapture,
    duration_tolerance_ratio: float = 0.15,
) -> bool:
    """İki yakalama aynı deseni temsil ediyor mu?"""
    if left.bits is not None and right.bits is not None:
        return left.bits == right.bits

    if len(left.pulses) != len(right.pulses):
        return False

    for lp, rp in zip(left.pulses, right.pulses, strict=True):
        if lp.level != rp.level:
            return False
        ref = max(lp.duration_s, rp.duration_s, 1e-9)
        if abs(lp.duration_s - rp.duration_s) > duration_tolerance_ratio * ref:
            return False
    return True


def assess_rolling_code(captures: list[OokCapture]) -> RollingCodeAssessment:
    """Aynı düğmeye birden fazla yakalama varsa kayan kod riskini değerlendir."""
    count = len(captures)
    if count < 2:
        return RollingCodeAssessment(
            status="insufficient_data",
            message="Kayan kod analizi için en az iki yakalama gerekli.",
            capture_count=count,
            matching_pairs=0,
            differing_pairs=0,
        )

    matching = 0
    differing = 0
    for i in range(count):
        for j in range(i + 1, count):
            if captures_equivalent(captures[i], captures[j]):
                matching += 1
            else:
                differing += 1

    if differing == 0:
        return RollingCodeAssessment(
            status="stable",
            message=(
                "Tüm yakalamalar aynı deseni gösteriyor; "
                "sabit kod veya replay ile uyumlu görünüyor."
            ),
            capture_count=count,
            matching_pairs=matching,
            differing_pairs=differing,
        )

    return RollingCodeAssessment(
        status="probably_rolling",
        message=(
            "Yakalamalar birbirinden farklı; bu muhtemelen kayan kod kullanıyor. "
            "Replay çalışmayabilir."
        ),
        capture_count=count,
        matching_pairs=matching,
        differing_pairs=differing,
    )


def _segment_to_pulse(
    start_idx: int,
    end_idx: int,
    sample_rate: float,
    level: bool,
) -> PulseEvent:
    start_s = start_idx / sample_rate
    end_s = end_idx / sample_rate
    return PulseEvent(
        start_s=start_s,
        end_s=end_s,
        duration_s=end_s - start_s,
        level=level,
    )


def _filter_glitch_pulses(
    pulses: list[PulseEvent],
    min_duration_s: float,
) -> list[PulseEvent]:
    if min_duration_s <= 0:
        return list(pulses)
    return [p for p in pulses if p.duration_s >= min_duration_s]


def _decode_high_low_pairs(pulses: list[PulseEvent]) -> list[int] | None:
    """PT2262 benzeri: kısa YÜKSEK + uzun DÜŞÜK = 0, uzun YÜKSEK + kısa DÜŞÜK = 1."""
    pairs: list[tuple[float, float]] = []
    idx = 0
    while idx < len(pulses):
        pulse = pulses[idx]
        if not pulse.level:
            idx += 1
            continue
        if idx + 1 >= len(pulses):
            break
        low = pulses[idx + 1]
        if low.level:
            idx += 1
            continue
        pairs.append((pulse.duration_s, low.duration_s))
        idx += 2

    if len(pairs) < 2:
        return None

    highs = np.array([h for h, _ in pairs], dtype=np.float64)
    lows = np.array([l for _, l in pairs], dtype=np.float64)
    min_duration = min(float(highs.min()), float(lows.min()))
    if min_duration <= 0:
        return None

    filtered: list[tuple[float, float]] = []
    glitch_limit = min_duration * 0.35
    for high, low in pairs:
        if high < glitch_limit or low < glitch_limit:
            continue
        filtered.append((high, low))

    if len(filtered) < 2:
        return None

    bits: list[int] = []
    for high, low in filtered:
        if high == low:
            return None
        bits.append(1 if high > low else 0)
    return bits


def _decode_on_pulse_widths(pulses: list[PulseEvent]) -> list[int] | None:
    """ON darbe genişliği kodlaması: kısa ON = 0, uzun ON = 1."""
    on_durations = [p.duration_s for p in pulses if p.level]
    if len(on_durations) < 2:
        return None

    min_on = min(on_durations)
    filtered = [d for d in on_durations if d >= min_on * 0.6]
    if len(filtered) < 2:
        return None

    durations = np.array(filtered, dtype=np.float64)
    short_ref = float(np.min(durations))
    long_ref = float(np.max(durations))
    if long_ref / short_ref < 1.35:
        return None

    threshold = (short_ref + long_ref) * 0.5
    bits = [1 if d >= threshold else 0 for d in filtered]
    if len(bits) < 2:
        return None
    return bits
