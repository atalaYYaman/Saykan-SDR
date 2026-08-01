"""Tests for mock signal scenarios and absolute-RF tuning."""

from __future__ import annotations

import numpy as np

from sdr_console.dsp.spectrum import compute_spectrum_frame
from sdr_console.hal.mock_device import DEFAULT_CENTER_FREQ_HZ, MockSDRDevice, MockTone
from sdr_console.hal.scenarios import burst_tone, clipping_source, noise_only, sweep_tone


def test_out_of_band_tone_is_silent() -> None:
    center = DEFAULT_CENTER_FREQ_HZ
    device = MockSDRDevice(
        center_freq_hz=center,
        tones=(MockTone(center + 5_000_000.0, 1.0),),
        noise_amplitude=0.0,
        gain_db=50.0,
    )
    device.connect()
    iq = device.read_samples(1024)
    device.disconnect()
    assert float(np.max(np.abs(iq))) < 1e-6


def test_sample_rate_250k_accepted() -> None:
    device = MockSDRDevice()
    device.set_sample_rate(250_000.0)
    assert device.sample_rate_hz == 250_000.0


def test_sweep_peak_moves_over_time() -> None:
    fft_size = 1024
    sample_rate = 2_048_000.0
    device = sweep_tone(
        start_offset_hz=-100_000.0,
        end_offset_hz=100_000.0,
        duration_s=0.01,
        sample_rate_hz=sample_rate,
    )
    device.connect()
    first = device.read_samples(fft_size)
    # Advance far into the sweep.
    for _ in range(20):
        device.read_samples(fft_size)
    last = device.read_samples(fft_size)
    device.disconnect()

    frame_first = compute_spectrum_frame(
        first, fft_size, device.center_freq_hz, sample_rate, timestamp=0.0
    )
    frame_last = compute_spectrum_frame(
        last, fft_size, device.center_freq_hz, sample_rate, timestamp=0.0
    )
    assert int(np.argmax(frame_last.db_values)) > int(np.argmax(frame_first.db_values))


def test_burst_has_on_and_off_energy() -> None:
    sample_rate = 2_048_000.0
    device = burst_tone(
        offset_hz=50_000.0,
        period_s=0.001,
        duty_cycle=0.5,
        sample_rate_hz=sample_rate,
    )
    device.set_gain(50.0)
    device._noise_amplitude = 0.005
    device.connect()
    # Collect several periods worth of samples.
    block = device.read_samples(int(sample_rate * 0.005))
    device.disconnect()

    chunk = 512
    energies = [
        float(np.mean(np.abs(block[i : i + chunk]) ** 2))
        for i in range(0, block.size - chunk, chunk)
    ]
    assert max(energies) > 5 * min(energies)


def test_noise_only_has_no_strong_peak() -> None:
    device = noise_only(noise_amplitude=0.02)
    device.connect()
    iq = device.read_samples(1024)
    device.disconnect()
    frame = compute_spectrum_frame(
        iq, 1024, device.center_freq_hz, device.sample_rate_hz, timestamp=0.0
    )
    assert float(np.max(frame.db_values)) < -20.0


def test_clipping_source_near_full_scale() -> None:
    device = clipping_source()
    device.connect()
    iq = device.read_samples(1024)
    device.disconnect()
    frame = compute_spectrum_frame(
        iq, 1024, device.center_freq_hz, device.sample_rate_hz, timestamp=0.0
    )
    assert float(np.max(frame.db_values)) > -3.0
