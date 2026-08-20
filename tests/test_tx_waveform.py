"""Bant sınırlı gürültü + CW test-sinyali."""

from __future__ import annotations

import numpy as np
import pytest

from sdr_console.tx.constants import PLUTO_MIN_TX_RF_BANDWIDTH_HZ
from sdr_console.tx.waveform import (
    analog_tx_rf_bandwidth_hz,
    clamp_bandwidth_hz,
    generate_noise_plus_tone,
)


def test_clamp_bandwidth_caps_at_sample_rate() -> None:
    assert clamp_bandwidth_hz(5_000_000.0, 2_048_000.0) == pytest.approx(2_048_000.0)
    with pytest.raises(ValueError):
        clamp_bandwidth_hz(0.0, 1_000_000.0)


def test_analog_tx_rf_bandwidth_respects_ad9363_floor() -> None:
    analog = analog_tx_rf_bandwidth_hz(25_000.0, 2_048_000.0)
    assert analog == pytest.approx(PLUTO_MIN_TX_RF_BANDWIDTH_HZ)


def test_noise_plus_tone_has_dc_and_in_band_energy() -> None:
    rate = 2_048_000.0
    bandwidth = 100_000.0
    iq = generate_noise_plus_tone(
        rate,
        bandwidth,
        num_samples=8192,
        rng=np.random.default_rng(0),
    )
    assert iq.dtype == np.complex64
    assert iq.shape == (8192,)
    assert float(np.max(np.abs(iq))) <= 1.0 + 1e-5

    spec = np.abs(np.fft.fft(iq))
    freqs = np.fft.fftfreq(iq.size, d=1.0 / rate)
    dc = float(spec[0])
    in_band = spec[np.abs(freqs) <= bandwidth / 2.0]
    out_band = spec[np.abs(freqs) > bandwidth * 0.7]
    assert dc > float(np.median(in_band))
    assert float(np.median(out_band)) < float(np.median(in_band)) * 0.2
