"""TX yayınının RX yakalamasıyla doğrulanması."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from sdr_console.tx.capture_decoder import (
    OokCapture,
    analyze_capture,
    captures_equivalent,
    threshold_to_bits,
)
from sdr_console.tx.ook_encoder import encode_capture


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Doğrulama sonucu ve kısa gerekçe."""

    passed: bool
    envelope_correlation: float
    pulse_match_ratio: float
    message: str


def verify_transmission(
    original_capture: OokCapture,
    verification_capture: OokCapture,
    *,
    duration_tolerance_ratio: float = 0.15,
    envelope_correlation_min: float = 0.85,
    min_pulse_match_ratio: float = 0.8,
    amplitude: float = 0.85,
    original_iq: np.ndarray | None = None,
    verification_iq: np.ndarray | None = None,
) -> bool:
    """Orijinal yakalama ile doğrulama yakalamasını karşılaştır.

    Darbe zamanlaması ve zarf benzerliği birlikte değerlendirilir. Loopback
    senaryosunda ``verification_iq`` verildiğinde zarf korelasyonu ham RX
    üzerinden hesaplanır (gürültülü decode yerine).
    """
    return assess_transmission(
        original_capture,
        verification_capture,
        duration_tolerance_ratio=duration_tolerance_ratio,
        envelope_correlation_min=envelope_correlation_min,
        min_pulse_match_ratio=min_pulse_match_ratio,
        amplitude=amplitude,
        original_iq=original_iq,
        verification_iq=verification_iq,
    ).passed


def assess_transmission(
    original_capture: OokCapture,
    verification_capture: OokCapture,
    *,
    duration_tolerance_ratio: float = 0.15,
    envelope_correlation_min: float = 0.85,
    min_pulse_match_ratio: float = 0.8,
    amplitude: float = 0.85,
    original_iq: np.ndarray | None = None,
    verification_iq: np.ndarray | None = None,
) -> VerificationResult:
    """Doğrulama sonucunu ayrıntılı metriklerle döndür."""
    if captures_equivalent(
        original_capture,
        verification_capture,
        duration_tolerance_ratio=duration_tolerance_ratio,
    ):
        return VerificationResult(
            passed=True,
            envelope_correlation=1.0,
            pulse_match_ratio=1.0,
            message="Darbe zamanlaması birebir eşleşiyor.",
        )

    if (
        original_capture.bits is not None
        and verification_capture.bits is not None
        and original_capture.bits == verification_capture.bits
    ):
        return VerificationResult(
            passed=True,
            envelope_correlation=1.0,
            pulse_match_ratio=1.0,
            message="Çözülen bit dizileri eşleşiyor.",
        )

    envelope_corr = _envelope_correlation(
        original_capture,
        verification_capture,
        amplitude=amplitude,
        original_iq=original_iq,
        verification_iq=verification_iq,
    )
    if verification_iq is not None:
        left_iq = (
            original_iq
            if original_iq is not None
            else encode_capture(original_capture, amplitude=amplitude)
        )
        pulse_ratio = _pulse_timing_match_from_iq(
            left_iq,
            verification_iq,
            original_capture.sample_rate_hz,
            duration_tolerance_ratio=duration_tolerance_ratio,
        )
    else:
        pulse_ratio = _pulse_timing_match_ratio(
            original_capture,
            verification_capture,
            duration_tolerance_ratio=duration_tolerance_ratio,
        )

    passed = (
        envelope_corr >= envelope_correlation_min
        and pulse_ratio >= min_pulse_match_ratio
    )
    if passed:
        message = (
            f"Zarf korelasyonu ({envelope_corr:.2f}) ve darbe eşleşmesi "
            f"({pulse_ratio:.2f}) eşikleri geçti."
        )
    else:
        message = (
            f"Doğrulama başarısız: zarf korelasyonu={envelope_corr:.2f} "
            f"(min {envelope_correlation_min:.2f}), "
            f"darbe eşleşmesi={pulse_ratio:.2f} "
            f"(min {min_pulse_match_ratio:.2f})."
        )

    return VerificationResult(
        passed=passed,
        envelope_correlation=envelope_corr,
        pulse_match_ratio=pulse_ratio,
        message=message,
    )


def simulate_loopback_iq(
    original_capture: OokCapture,
    *,
    amplitude: float = 0.85,
    loopback_attenuation_db: float = 20.0,
    noise_amplitude: float = 0.02,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Kablo loopback IQ simülasyonu (OTA yok): encode → zayıflat → gürültü."""
    if loopback_attenuation_db < 0:
        raise ValueError("loopback_attenuation_db must be non-negative")
    if amplitude <= 0:
        raise ValueError("amplitude must be positive")
    if noise_amplitude < 0:
        raise ValueError("noise_amplitude must be non-negative")

    iq = encode_capture(original_capture, amplitude=amplitude)
    scale = 10.0 ** (-loopback_attenuation_db / 20.0)
    looped = iq * np.float32(scale)

    if noise_amplitude > 0.0:
        generator = rng or np.random.default_rng(0)
        noise = generator.normal(0.0, noise_amplitude, looped.size)
        noise_j = generator.normal(0.0, noise_amplitude, looped.size)
        looped = looped + (noise + 1j * noise_j).astype(np.complex64)

    return looped


def simulate_loopback_capture(
    original_capture: OokCapture,
    *,
    amplitude: float = 0.85,
    loopback_attenuation_db: float = 20.0,
    noise_amplitude: float = 0.02,
    rng: np.random.Generator | None = None,
) -> OokCapture:
    """Loopback IQ üret ve RX yakalaması olarak analiz et."""
    looped = simulate_loopback_iq(
        original_capture,
        amplitude=amplitude,
        loopback_attenuation_db=loopback_attenuation_db,
        noise_amplitude=noise_amplitude,
        rng=rng,
    )

    peak = float(np.max(np.abs(looped)))
    floor = float(np.min(np.abs(looped)))
    threshold = (peak + floor) * 0.5 if peak > floor else peak * 0.5

    return analyze_capture(
        looped,
        original_capture.sample_rate_hz,
        threshold=threshold,
    )


def _envelope_correlation(
    left: OokCapture,
    right: OokCapture,
    amplitude: float,
    original_iq: np.ndarray | None = None,
    verification_iq: np.ndarray | None = None,
) -> float:
    if original_iq is not None:
        left_env = np.abs(np.asarray(original_iq).reshape(-1))
    else:
        left_env = np.abs(encode_capture(left, amplitude=amplitude))

    if verification_iq is not None:
        right_env = np.abs(np.asarray(verification_iq).reshape(-1))
    else:
        right_env = np.abs(encode_capture(right, amplitude=amplitude))

    left_env = _smooth_envelope(left_env)
    right_env = _smooth_envelope(right_env)

    n = min(left_env.size, right_env.size)
    if n < 8:
        return 0.0

    a = left_env[:n]
    b = right_env[:n]
    a_peak = float(np.max(a))
    b_peak = float(np.max(b))
    if a_peak <= 0.0 or b_peak <= 0.0:
        return 0.0

    a_norm = a / a_peak
    b_norm = b / b_peak
    corr_matrix = np.corrcoef(a_norm, b_norm)
    corr = float(corr_matrix[0, 1])
    if np.isnan(corr):
        return 0.0
    return corr


def _pulse_timing_match_from_iq(
    original_iq: np.ndarray,
    verification_iq: np.ndarray,
    sample_rate_hz: float,
    duration_tolerance_ratio: float,
) -> float:
    """Gürültülü loopback için zarf üzerinden darbe zamanlaması karşılaştır."""
    left_env = _smooth_envelope(np.abs(np.asarray(original_iq).reshape(-1)))
    right_env = _smooth_envelope(np.abs(np.asarray(verification_iq).reshape(-1)))

    left_peak = float(np.max(left_env))
    right_peak = float(np.max(right_env))
    if left_peak <= 0.0 or right_peak <= 0.0:
        return 0.0

    left_pulses = threshold_to_bits(left_env, left_peak * 0.45, sample_rate_hz)
    right_pulses = threshold_to_bits(right_env, right_peak * 0.45, sample_rate_hz)

    left_capture = OokCapture(
        pulses=tuple(left_pulses),
        bits=None,
        sample_rate_hz=sample_rate_hz,
        threshold=left_peak * 0.45,
    )
    right_capture = OokCapture(
        pulses=tuple(right_pulses),
        bits=None,
        sample_rate_hz=sample_rate_hz,
        threshold=right_peak * 0.45,
    )
    return _pulse_timing_match_ratio(
        left_capture,
        right_capture,
        duration_tolerance_ratio=duration_tolerance_ratio,
    )


def _pulse_timing_match_ratio(
    left: OokCapture,
    right: OokCapture,
    duration_tolerance_ratio: float,
) -> float:
    left_ons = _significant_on_durations(left)
    if not left_ons:
        return 0.0

    reference_min_on = min(left_ons)
    right_ons = _significant_on_durations(right, reference_min_on=reference_min_on)
    if not right_ons:
        return 0.0

    count_ratio = min(len(left_ons), len(right_ons)) / max(len(left_ons), len(right_ons))
    pair_count = min(len(left_ons), len(right_ons))

    matches = 0
    for idx in range(pair_count):
        ref = max(left_ons[idx], right_ons[idx], 1e-9)
        if abs(left_ons[idx] - right_ons[idx]) <= duration_tolerance_ratio * ref:
            matches += 1

    return (matches / len(left_ons)) * count_ratio


def _significant_on_durations(
    capture: OokCapture,
    reference_min_on: float | None = None,
) -> list[float]:
    """Gürültü spike'larını filtrele; doğrulama tarafında referans ölçek kullan."""
    on_durations = [pulse.duration_s for pulse in capture.pulses if pulse.level]
    if not on_durations:
        return []

    base_min = reference_min_on if reference_min_on is not None else min(on_durations)
    glitch_limit = max(base_min * 0.45, 1e-7)
    return [duration for duration in on_durations if duration >= glitch_limit]


def _smooth_envelope(envelope: np.ndarray, window: int = 9) -> np.ndarray:
    if envelope.size < window:
        return envelope.astype(np.float64, copy=False)
    kernel = np.ones(window, dtype=np.float64) / window
    return np.convolve(envelope.astype(np.float64), kernel, mode="same")
