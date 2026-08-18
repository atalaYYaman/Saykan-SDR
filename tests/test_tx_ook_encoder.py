"""OOK encoder round-trip ve replay_capture testleri."""

from __future__ import annotations

import numpy as np
import pytest

from sdr_console.tx.capture_decoder import analyze_capture, captures_equivalent
from sdr_console.tx.errors import ReplayNotConfirmedError
from sdr_console.tx.mock_tx import MockTXDevice
from sdr_console.tx.ook_encoder import encode_capture, encode_from_pulses, encode_ook
from sdr_console.tx.replay import replay_capture

SAMPLE_RATE_HZ = 2_000_000.0
BIT_DURATION_S = 0.0003
AMPLITUDE = 0.85
THRESHOLD = AMPLITUDE * 0.5


def test_encode_ook_decode_roundtrip() -> None:
    bits = [1, 0, 1, 1, 0, 0, 1]
    iq = encode_ook(bits, BIT_DURATION_S, SAMPLE_RATE_HZ, AMPLITUDE)
    capture = analyze_capture(iq, SAMPLE_RATE_HZ, threshold=THRESHOLD)

    assert capture.bits is not None
    assert list(capture.bits) == bits


def test_encode_from_pulses_preserves_timing() -> None:
    bits = [0, 1, 0, 1, 1, 0]
    # PT2262 benzeri sentetik yakalama
    original_iq = _synthesize_pt2262(bits)
    original = analyze_capture(original_iq, SAMPLE_RATE_HZ, threshold=THRESHOLD)

    reencoded = encode_from_pulses(list(original.pulses), SAMPLE_RATE_HZ, AMPLITUDE)
    recovered = analyze_capture(reencoded, SAMPLE_RATE_HZ, threshold=THRESHOLD)

    assert captures_equivalent(original, recovered)
    assert recovered.bits is not None
    assert list(recovered.bits) == bits


def test_encode_capture_uses_pulses_when_available() -> None:
    bits = [1, 0, 1]
    original = analyze_capture(
        encode_ook(bits, BIT_DURATION_S, SAMPLE_RATE_HZ, AMPLITUDE),
        SAMPLE_RATE_HZ,
        threshold=THRESHOLD,
    )
    iq = encode_capture(original, amplitude=AMPLITUDE)
    recovered = analyze_capture(iq, SAMPLE_RATE_HZ, threshold=THRESHOLD)

    assert captures_equivalent(original, recovered)


def test_replay_capture_requires_confirmation() -> None:
    device = MockTXDevice()
    capture = analyze_capture(
        encode_ook([1, 0], BIT_DURATION_S, SAMPLE_RATE_HZ, AMPLITUDE),
        SAMPLE_RATE_HZ,
        threshold=THRESHOLD,
    )

    with pytest.raises(ReplayNotConfirmedError, match="confirmation"):
        replay_capture(device, capture, attenuation_db=50.0, max_duration_s=1.0)


def test_replay_capture_transmits_when_confirmed() -> None:
    device = MockTXDevice()
    bits = [1, 0, 1, 1]
    capture = analyze_capture(
        encode_ook(bits, BIT_DURATION_S, SAMPLE_RATE_HZ, AMPLITUDE),
        SAMPLE_RATE_HZ,
        threshold=THRESHOLD,
    )

    sent = replay_capture(
        device,
        capture,
        attenuation_db=50.0,
        max_duration_s=0.2,
        confirmed=True,
    )

    assert device.is_transmitting
    assert sent.shape[0] > 0
    assert device.transmitted_iq is not None
    assert np.array_equal(device.transmitted_iq, sent)
    device.stop_tx()


def _synthesize_pt2262(bits: list[int]) -> np.ndarray:
    short_s = BIT_DURATION_S
    long_s = BIT_DURATION_S * 2.0
    segments: list[np.ndarray] = []
    for bit in bits:
        if bit:
            on_s, off_s = long_s, short_s
        else:
            on_s, off_s = short_s, long_s
        n_on = max(1, int(round(on_s * SAMPLE_RATE_HZ)))
        n_off = max(1, int(round(off_s * SAMPLE_RATE_HZ)))
        segments.append(np.full(n_on, AMPLITUDE, dtype=np.float32))
        segments.append(np.zeros(n_off, dtype=np.float32))
    return np.concatenate(segments).astype(np.complex64)
