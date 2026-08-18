"""Unit tests for audio bandwidth (AFBW) filtering (ADIM A4)."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.signal import freqz

from sdr_console.demod.am import AMDemodulator
from sdr_console.demod.cw import CWDemodulator
from sdr_console.demod.factory import DEFAULT_AFBW_HZ, default_afbw_hz
from sdr_console.demod.fm import NFMDemodulator, WFMDemodulator
from sdr_console.demod.ssb import USBDemodulator
from sdr_console.dsp.afbw import (
    AFBW_CW_HZ,
    AFBW_SPEECH_HZ,
    AFBW_SSB_HZ,
    AFBW_WFM_HZ,
    AudioBandwidthFilter,
    design_afbw_lpf,
)


def test_design_afbw_passes_in_band_and_stops_high_frequencies() -> None:
    sample_rate_hz = 48_000.0
    cutoff_hz = 4_000.0
    taps = design_afbw_lpf(cutoff_hz, sample_rate_hz)
    _w, h = freqz(taps, [1.0], worN=4096, fs=sample_rate_hz)
    freqs = _w
    magnitude_db = 20.0 * np.log10(np.maximum(np.abs(h), 1e-12))

    in_band = magnitude_db[freqs <= cutoff_hz * 0.5]
    far_out = magnitude_db[freqs >= 12_000.0]
    assert np.all(in_band > -1.5)
    assert np.all(far_out < -35.0)


def test_afbw_suppresses_high_frequency_noise_on_a_tone() -> None:
    """Speech-tone + HF noise: after AFBW the noise power drops sharply."""
    sample_rate_hz = 48_000.0
    cutoff_hz = 4_000.0
    n = 48_000
    rng = np.random.default_rng(0)
    t = np.arange(n, dtype=np.float64) / sample_rate_hz
    tone = 0.5 * np.sin(2.0 * np.pi * 1_000.0 * t)
    noise = 0.5 * rng.standard_normal(n)
    # Band-limit the noise to 8–16 kHz so AFBW must reject it.
    noise_fft = np.fft.rfft(noise)
    freqs = np.fft.rfftfreq(n, d=1.0 / sample_rate_hz)
    noise_fft[(freqs < 8_000.0) | (freqs > 16_000.0)] = 0.0
    hf_noise = np.fft.irfft(noise_fft, n=n)
    hf_noise *= 0.5 / max(float(np.std(hf_noise)), 1e-12)

    mixed = tone + hf_noise
    filtered = AudioBandwidthFilter(cutoff_hz, sample_rate_hz).process(mixed)
    settle = slice(n // 4, None)

    def band_power(signal: np.ndarray, low_hz: float, high_hz: float) -> float:
        spectrum = np.fft.rfft(signal[settle] * np.hanning(signal[settle].size))
        band_freqs = np.fft.rfftfreq(signal[settle].size, d=1.0 / sample_rate_hz)
        mask = (band_freqs >= low_hz) & (band_freqs <= high_hz)
        return float(np.sum(np.abs(spectrum[mask]) ** 2))

    tone_before = band_power(mixed, 800.0, 1_200.0)
    tone_after = band_power(filtered, 800.0, 1_200.0)
    noise_before = band_power(mixed, 8_000.0, 16_000.0)
    noise_after = band_power(filtered, 8_000.0, 16_000.0)

    assert tone_after / max(tone_before, 1e-18) > 0.7
    assert 10.0 * np.log10(noise_after / max(noise_before, 1e-18)) < -30.0


def test_mode_default_afbw_table() -> None:
    assert default_afbw_hz("AM") == AFBW_SPEECH_HZ
    assert default_afbw_hz("N-FM") == AFBW_SPEECH_HZ
    assert default_afbw_hz("W-FM") == AFBW_WFM_HZ
    assert default_afbw_hz("USB") == AFBW_SSB_HZ
    assert default_afbw_hz("LSB") == AFBW_SSB_HZ
    assert default_afbw_hz("CW") == AFBW_CW_HZ
    assert DEFAULT_AFBW_HZ["W-FM"] == AFBW_WFM_HZ


@pytest.mark.parametrize(
    ("cls", "expected"),
    [
        (AMDemodulator, AFBW_SPEECH_HZ),
        (NFMDemodulator, AFBW_SPEECH_HZ),
        (WFMDemodulator, AFBW_WFM_HZ),
        (USBDemodulator, AFBW_SSB_HZ),
        (CWDemodulator, AFBW_CW_HZ),
    ],
)
def test_demodulators_expose_default_afbw(cls, expected: float) -> None:
    rate = 48_000.0 if cls is not WFMDemodulator else 240_000.0
    decimation = 1 if cls is not WFMDemodulator else 5
    demod = cls(input_rate_hz=rate, audio_decimation=decimation)
    assert demod.afbw_hz == pytest.approx(expected)


def test_afbw_override_is_honoured() -> None:
    demod = AMDemodulator(input_rate_hz=48_000.0, audio_decimation=1, afbw_hz=2_700.0)
    assert demod.afbw_hz == pytest.approx(2_700.0)
