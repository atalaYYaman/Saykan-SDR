"""OOK yakalama, decode ve kayan kod tespiti testleri."""

from __future__ import annotations

import numpy as np
import pytest

from sdr_console.tx.capture_decoder import (
    analyze_capture,
    assess_rolling_code,
    decode_ook_pulses,
    envelope_detect,
    threshold_to_bits,
)

SAMPLE_RATE_HZ = 2_000_000.0
SHORT_S = 0.0003
LONG_S = 0.0006
GAP_S = 0.0003
AMPLITUDE = 0.85


def synthesize_on_width_ook(
    bits: list[int],
    sample_rate: float = SAMPLE_RATE_HZ,
    short_s: float = SHORT_S,
    long_s: float = LONG_S,
    gap_s: float = GAP_S,
    amplitude: float = AMPLITUDE,
) -> np.ndarray:
    """ON genişliği kodlaması: 0 = kısa ON, 1 = uzun ON; her bit arasında boşluk."""
    segments: list[np.ndarray] = []
    for bit in bits:
        on_s = long_s if bit else short_s
        n_on = max(1, int(on_s * sample_rate))
        n_gap = max(1, int(gap_s * sample_rate))
        segments.append(np.full(n_on, amplitude, dtype=np.float32))
        segments.append(np.zeros(n_gap, dtype=np.float32))
    envelope = np.concatenate(segments)
    return envelope.astype(np.complex64)


def synthesize_pt2262_ook(
    bits: list[int],
    sample_rate: float = SAMPLE_RATE_HZ,
    short_s: float = SHORT_S,
    long_s: float = LONG_S,
    amplitude: float = AMPLITUDE,
) -> np.ndarray:
    """PT2262 benzeri: 0 = kısa ON + uzun OFF, 1 = uzun ON + kısa OFF."""
    segments: list[np.ndarray] = []
    for bit in bits:
        if bit:
            on_s, off_s = long_s, short_s
        else:
            on_s, off_s = short_s, long_s
        n_on = max(1, int(on_s * sample_rate))
        n_off = max(1, int(off_s * sample_rate))
        segments.append(np.full(n_on, amplitude, dtype=np.float32))
        segments.append(np.zeros(n_off, dtype=np.float32))
    envelope = np.concatenate(segments)
    return envelope.astype(np.complex64)


def test_envelope_detect_is_absolute_value() -> None:
    iq = np.array([1.0 + 0j, -2.0 + 0j, 0.0 - 3.0j], dtype=np.complex64)
    envelope = envelope_detect(iq)
    assert envelope[0] == pytest.approx(1.0)
    assert envelope[1] == pytest.approx(2.0)
    assert envelope[2] == pytest.approx(3.0)


def test_on_width_ook_decode_roundtrip() -> None:
    bits = [1, 0, 1, 1, 0, 0, 1]
    iq = synthesize_on_width_ook(bits)
    capture = analyze_capture(iq, SAMPLE_RATE_HZ, threshold=AMPLITUDE * 0.5)

    assert capture.bits is not None
    assert list(capture.bits) == bits
    assert len(capture.pulses) > 0


def test_pt2262_style_decode_roundtrip() -> None:
    bits = [0, 1, 0, 1, 1, 0]
    iq = synthesize_pt2262_ook(bits)
    capture = analyze_capture(iq, SAMPLE_RATE_HZ, threshold=AMPLITUDE * 0.5)

    assert capture.bits is not None
    assert list(capture.bits) == bits


def test_threshold_to_bits_reports_pulse_timing() -> None:
    iq = synthesize_on_width_ook([1, 0])
    envelope = envelope_detect(iq)
    pulses = threshold_to_bits(envelope, AMPLITUDE * 0.5, SAMPLE_RATE_HZ)

    on_pulses = [p for p in pulses if p.level]
    assert len(on_pulses) == 2
    assert on_pulses[0].duration_s == pytest.approx(LONG_S, rel=0.08)
    assert on_pulses[1].duration_s == pytest.approx(SHORT_S, rel=0.08)


def test_decode_ook_pulses_returns_none_for_empty() -> None:
    assert decode_ook_pulses([]) is None


def test_rolling_code_stable_when_captures_match() -> None:
    bits = [1, 0, 1, 1, 0]
    iq = synthesize_on_width_ook(bits)
    captures = [
        analyze_capture(iq, SAMPLE_RATE_HZ, threshold=AMPLITUDE * 0.5),
        analyze_capture(iq, SAMPLE_RATE_HZ, threshold=AMPLITUDE * 0.5),
    ]
    report = assess_rolling_code(captures)

    assert report.status == "stable"
    assert report.differing_pairs == 0
    assert report.matching_pairs == 1
    assert "sabit" in report.message.lower() or "aynı" in report.message.lower()


def test_rolling_code_warning_when_captures_differ() -> None:
    capture_a = analyze_capture(
        synthesize_on_width_ook([1, 0, 1, 0, 1]),
        SAMPLE_RATE_HZ,
        threshold=AMPLITUDE * 0.5,
    )
    capture_b = analyze_capture(
        synthesize_on_width_ook([0, 1, 0, 1, 0, 1, 1]),
        SAMPLE_RATE_HZ,
        threshold=AMPLITUDE * 0.5,
    )
    report = assess_rolling_code([capture_a, capture_b])

    assert report.status == "probably_rolling"
    assert report.differing_pairs == 1
    assert "kayan kod" in report.message.lower()
    assert "replay" in report.message.lower()


def test_rolling_code_insufficient_data_with_single_capture() -> None:
    capture = analyze_capture(
        synthesize_on_width_ook([1, 0]),
        SAMPLE_RATE_HZ,
        threshold=AMPLITUDE * 0.5,
    )
    report = assess_rolling_code([capture])

    assert report.status == "insufficient_data"
    assert report.capture_count == 1
