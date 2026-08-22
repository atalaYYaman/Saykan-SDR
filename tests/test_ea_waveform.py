"""Baraj gürültüsü — CW yok, bant içi enerji."""

from __future__ import annotations

import numpy as np
import pytest

from sdr_console.ea.waveform import generate_barrage_noise
from sdr_console.tx.waveform import clamp_bandwidth_hz


def test_barrage_noise_is_unit_scale_without_dc_tone() -> None:
    rate = 2_048_000.0
    bandwidth = 500_000.0
    iq = generate_barrage_noise(
        rate,
        bandwidth,
        num_samples=8192,
        rng=np.random.default_rng(0),
    )
    assert iq.dtype == np.complex64
    assert iq.shape == (8192,)
    assert float(np.max(np.abs(iq))) <= 1.0 + 1e-5
    assert float(np.abs(np.mean(iq))) < 0.05

    spec = np.abs(np.fft.fft(iq))
    freqs = np.fft.fftfreq(iq.size, d=1.0 / rate)
    dc = float(spec[0])
    in_band = spec[np.abs(freqs) <= bandwidth / 2.0]
    out_band = spec[np.abs(freqs) > bandwidth * 0.7]
    assert dc < float(np.median(in_band)) * 5.0
    assert float(np.median(out_band)) < float(np.median(in_band)) * 0.2


def test_barrage_bandwidth_caps_at_sample_rate() -> None:
    assert clamp_bandwidth_hz(5_000_000.0, 2_048_000.0) == pytest.approx(2_048_000.0)
    iq = generate_barrage_noise(
        2_048_000.0,
        5_000_000.0,
        num_samples=4096,
        rng=np.random.default_rng(1),
    )
    assert iq.size == 4096
