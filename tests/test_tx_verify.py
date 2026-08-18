"""TX doğrulama ve loopback simülasyon testleri."""

from __future__ import annotations

import numpy as np
import pytest

from sdr_console.tx.capture_decoder import analyze_capture
from sdr_console.tx.ook_encoder import encode_ook
from sdr_console.tx.verify import (
    assess_transmission,
    simulate_loopback_capture,
    simulate_loopback_iq,
    verify_transmission,
)

SAMPLE_RATE_HZ = 2_000_000.0
BIT_DURATION_S = 0.0003
AMPLITUDE = 0.85
THRESHOLD = AMPLITUDE * 0.5


def _original_capture(bits: list[int]) -> object:
    iq = encode_ook(bits, BIT_DURATION_S, SAMPLE_RATE_HZ, AMPLITUDE)
    return analyze_capture(iq, SAMPLE_RATE_HZ, threshold=THRESHOLD)


def test_verify_transmission_passes_for_simulated_loopback() -> None:
    original = _original_capture([1, 0, 1, 1, 0, 0, 1])
    looped_iq = simulate_loopback_iq(
        original,
        amplitude=AMPLITUDE,
        loopback_attenuation_db=25.0,
        noise_amplitude=0.012,
    )
    verification = analyze_capture(
        looped_iq,
        SAMPLE_RATE_HZ,
        threshold=float(np.max(np.abs(looped_iq)) * 0.45),
    )

    assert verify_transmission(
        original,
        verification,
        verification_iq=looped_iq,
    )
    result = assess_transmission(
        original,
        verification,
        verification_iq=looped_iq,
    )
    assert result.passed
    assert result.envelope_correlation >= 0.85
    assert result.pulse_match_ratio >= 0.8


def test_verify_transmission_fails_for_different_pattern() -> None:
    original = _original_capture([1, 0, 1, 0, 1])
    different = _original_capture([0, 1, 0, 1, 0, 1, 1])

    assert not verify_transmission(original, different)
    result = assess_transmission(original, different)
    assert not result.passed


def test_simulate_loopback_without_noise_still_verifies() -> None:
    bits = [0, 1, 1, 0, 1]
    original = _original_capture(bits)
    looped_iq = simulate_loopback_iq(
        original,
        loopback_attenuation_db=30.0,
        noise_amplitude=0.0,
    )
    verification = simulate_loopback_capture(
        original,
        loopback_attenuation_db=30.0,
        noise_amplitude=0.0,
    )

    assert verify_transmission(original, verification, verification_iq=looped_iq)
    assert verification.bits is not None
    assert list(verification.bits) == bits


def test_loopback_chain_encode_replay_verify_without_hardware() -> None:
    """Tam yazılım zinciri: yakalama → encode → loopback RX → doğrulama."""
    bits = [1, 0, 1, 1, 0]
    original = _original_capture(bits)
    tx_iq = encode_ook(bits, BIT_DURATION_S, SAMPLE_RATE_HZ, AMPLITUDE)

    looped = tx_iq * np.float32(0.05)
    rng = np.random.default_rng(7)
    noise = (
        rng.normal(0, 0.008, looped.size) + 1j * rng.normal(0, 0.008, looped.size)
    ).astype(np.complex64)
    looped = looped + noise

    verification = analyze_capture(
        looped,
        SAMPLE_RATE_HZ,
        threshold=float(np.max(np.abs(looped)) * 0.45),
    )

    assert verify_transmission(original, verification, verification_iq=looped)
