"""Unit tests for mock SDR device and capabilities."""

import numpy as np
import pytest

from sdr_console.dsp.spectrum import compute_spectrum_frame
from sdr_console.hal.mock_device import (
    DEFAULT_CENTER_FREQ_HZ,
    MOCK_CAPABILITIES,
    MockSDRDevice,
    MockTone,
)


def test_mock_device_requires_connection() -> None:
    device = MockSDRDevice()
    with pytest.raises(RuntimeError):
        device.read_samples(128)


def test_mock_device_returns_complex64() -> None:
    device = MockSDRDevice()
    device.connect()
    samples = device.read_samples(256)
    device.disconnect()

    assert samples.shape == (256,)
    assert samples.dtype == np.complex64


def test_capabilities_validate_ranges() -> None:
    caps = MOCK_CAPABILITIES

    with pytest.raises(ValueError):
        caps.validate_freq_hz(caps.min_freq_hz - 1.0)
    with pytest.raises(ValueError):
        caps.validate_sample_rate_hz(999_999.0)
    with pytest.raises(ValueError):
        caps.validate_gain_db(caps.max_gain_db + 1.0)


def test_setters_enforce_capabilities() -> None:
    device = MockSDRDevice()

    with pytest.raises(ValueError):
        device.set_center_freq(MOCK_CAPABILITIES.max_freq_hz + 1.0)
    with pytest.raises(ValueError):
        device.set_sample_rate(999_999.0)
    with pytest.raises(ValueError):
        device.set_gain(-1.0)


def test_read_samples_advances_time_at_sample_rate() -> None:
    sample_rate = 2_048_000.0
    center = DEFAULT_CENTER_FREQ_HZ
    tone_hz = 50_000.0
    device = MockSDRDevice(
        sample_rate_hz=sample_rate,
        center_freq_hz=center,
        tones=(MockTone(center + tone_hz, 1.0),),
        noise_amplitude=0.0,
    )
    device.connect()

    first = device.read_samples(1024)
    second = device.read_samples(1024)

    expected_phase_step = np.exp(2j * np.pi * tone_hz * 1024 / sample_rate)
    ratio = second[0] / first[0]
    assert ratio == pytest.approx(expected_phase_step, rel=1e-5, abs=1e-5)


def test_center_freq_shift_moves_baseband_peak() -> None:
    fft_size = 1024
    sample_rate = 2_048_000.0
    center = DEFAULT_CENTER_FREQ_HZ
    tone_rf = center + 50_000.0
    device = MockSDRDevice(
        sample_rate_hz=sample_rate,
        center_freq_hz=center,
        gain_db=50.0,
        tones=(MockTone(tone_rf, 1.0),),
        noise_amplitude=0.0,
    )
    device.connect()
    iq_before = device.read_samples(fft_size)

    device.set_center_freq(center + 50_000.0)
    iq_after = device.read_samples(fft_size)
    device.disconnect()

    frame_before = compute_spectrum_frame(
        iq_before, fft_size, center_freq=center, sample_rate=sample_rate, timestamp=0.0
    )
    frame_after = compute_spectrum_frame(
        iq_after,
        fft_size,
        center_freq=center + 50_000.0,
        sample_rate=sample_rate,
        timestamp=0.0,
    )

    peak_before = int(np.argmax(frame_before.db_values))
    peak_after = int(np.argmax(frame_after.db_values))
    bin_hz = sample_rate / fft_size

    assert peak_before == fft_size // 2 + int(round(50_000.0 / bin_hz))
    assert peak_after == fft_size // 2  # tone now at DC
    assert peak_after < peak_before


def test_tuning_far_away_hides_tones_without_error() -> None:
    center = DEFAULT_CENTER_FREQ_HZ
    device = MockSDRDevice(
        tones=(MockTone(center + 50_000.0, 1.0),),
        noise_amplitude=0.0,
        gain_db=50.0,
    )
    device.connect()
    device.set_center_freq(108_000_000.0)
    device.set_sample_rate(250_000.0)
    iq = device.read_samples(1024)
    device.disconnect()

    assert iq.dtype == np.complex64
    assert float(np.max(np.abs(iq))) < 1e-6


def test_multiple_tones_visible_in_spectrum() -> None:
    fft_size = 1024
    sample_rate = 2_048_000.0
    center = DEFAULT_CENTER_FREQ_HZ
    tone_offsets = (-120_000.0, 40_000.0, 180_000.0)
    device = MockSDRDevice(
        sample_rate_hz=sample_rate,
        center_freq_hz=center,
        gain_db=50.0,
        tones=tuple(MockTone(center + offset, 1.0) for offset in tone_offsets),
        noise_amplitude=0.0,
    )
    device.connect()
    iq = device.read_samples(fft_size)
    device.disconnect()

    frame = compute_spectrum_frame(
        iq,
        fft_size=fft_size,
        center_freq=center,
        sample_rate=sample_rate,
        timestamp=0.0,
    )
    bin_hz = sample_rate / fft_size

    for offset in tone_offsets:
        expected_bin = fft_size // 2 + int(round(offset / bin_hz))
        window = frame.db_values[expected_bin - 2 : expected_bin + 3]
        assert float(np.max(window)) > -20.0
