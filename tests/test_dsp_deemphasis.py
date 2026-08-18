"""Unit tests for FM de-emphasis (ADIM A3)."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.signal import freqz

from sdr_console.demod.fm import NFMDemodulator, WFMDemodulator
from sdr_console.dsp.audio import apply_iir
from sdr_console.dsp.deemphasis import (
    DEEMPHASIS_TAU_50_US,
    DEEMPHASIS_TAU_75_US,
    deemphasis_gain,
    design_deemphasis,
    preemphasis_gain,
    tau_seconds,
)


def test_tau_seconds_converts_microseconds() -> None:
    assert tau_seconds(75.0) == pytest.approx(75e-6)
    assert tau_seconds(50.0) == pytest.approx(50e-6)
    with pytest.raises(ValueError):
        tau_seconds(0.0)


def test_preemphasis_and_deemphasis_gains_are_inverses() -> None:
    tau = DEEMPHASIS_TAU_75_US
    for freq_hz in (100.0, 1_000.0, 5_000.0, 15_000.0):
        assert deemphasis_gain(freq_hz, tau) * preemphasis_gain(freq_hz, tau) == pytest.approx(
            1.0, rel=1e-12
        )


@pytest.mark.parametrize("tau_s", [DEEMPHASIS_TAU_50_US, DEEMPHASIS_TAU_75_US])
def test_design_deemphasis_matches_continuous_response(tau_s: float) -> None:
    sample_rate_hz = 48_000.0
    b, a = design_deemphasis(sample_rate_hz, tau_s)
    _w, h = freqz(b, a, worN=2048, fs=sample_rate_hz)
    freqs = _w
    # Stay well below Nyquist where the impulse-invariant map is accurate.
    mask = (freqs >= 200.0) & (freqs <= 12_000.0)
    measured_db = 20.0 * np.log10(np.maximum(np.abs(h[mask]), 1e-12))
    expected_db = 20.0 * np.log10(
        np.array([deemphasis_gain(float(f), tau_s) for f in freqs[mask]])
    )
    np.testing.assert_allclose(measured_db, expected_db, atol=1.5)


def test_deemphasis_restores_preemphasized_tone_balance() -> None:
    """High-frequency pre-emphasis is undone: relative levels return toward flat."""
    sample_rate_hz = 48_000.0
    tau_s = DEEMPHASIS_TAU_75_US
    low_hz, high_hz = 1_000.0, 10_000.0
    n = 48_000
    t = np.arange(n, dtype=np.float64) / sample_rate_hz

    # Flat tones, then apply continuous-time pre-emphasis gains (synthetic TX).
    low = np.sin(2.0 * np.pi * low_hz * t)
    high = np.sin(2.0 * np.pi * high_hz * t)
    preemphasized = (
        preemphasis_gain(low_hz, tau_s) * low + preemphasis_gain(high_hz, tau_s) * high
    )

    b, a = design_deemphasis(sample_rate_hz, tau_s)
    restored, _ = apply_iir(preemphasized, b, a)

    # Measure each tone via a narrow FFT bin after filtering.
    window = np.hanning(restored.size)
    spectrum = np.fft.rfft(restored * window)
    freqs = np.fft.rfftfreq(restored.size, d=1.0 / sample_rate_hz)

    def bin_mag(target_hz: float) -> float:
        index = int(np.argmin(np.abs(freqs - target_hz)))
        return float(np.abs(spectrum[index]))

    # Before de-emphasis the high tone is much louder; after, levels are close.
    pre_spectrum = np.fft.rfft(preemphasized * window)
    pre_high = float(np.abs(pre_spectrum[int(np.argmin(np.abs(freqs - high_hz)))]))
    pre_low = float(np.abs(pre_spectrum[int(np.argmin(np.abs(freqs - low_hz)))]))
    assert pre_high / pre_low > 2.0

    restored_ratio = bin_mag(high_hz) / bin_mag(low_hz)
    assert restored_ratio == pytest.approx(1.0, rel=0.15)


def test_wfm_enables_deemphasis_by_default_nfm_does_not() -> None:
    wfm = WFMDemodulator(240_000.0, audio_decimation=5)
    nfm = NFMDemodulator(48_000.0, audio_decimation=1)

    assert wfm.deemphasis_enabled
    assert wfm.deemphasis_tau_s == pytest.approx(DEEMPHASIS_TAU_75_US)
    assert not nfm.deemphasis_enabled
    assert nfm.deemphasis_tau_s is None


def test_nfm_can_enable_optional_deemphasis() -> None:
    nfm = NFMDemodulator(
        48_000.0,
        audio_decimation=1,
        deemphasis=True,
        deemphasis_tau_s=DEEMPHASIS_TAU_50_US,
    )
    assert nfm.deemphasis_enabled
    assert nfm.deemphasis_tau_s == pytest.approx(DEEMPHASIS_TAU_50_US)


def test_wfm_accepts_50_us_tau() -> None:
    wfm = WFMDemodulator(
        240_000.0,
        audio_decimation=5,
        deemphasis_tau_s=DEEMPHASIS_TAU_50_US,
    )
    assert wfm.deemphasis_tau_s == pytest.approx(DEEMPHASIS_TAU_50_US)
