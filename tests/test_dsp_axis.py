"""Unit tests for frequency axis math."""

from __future__ import annotations

import numpy as np
import pytest

from sdr_console.dsp.axis import (
    band_edges_hz,
    bin_to_freq_hz,
    clamp_freq_to_band,
    freq_to_bin,
    frequency_axis_hz,
)

CENTER_HZ = 100_000_000.0
SAMPLE_RATE_HZ = 2_048_000.0
FFT_SIZE = 1024


def test_axis_spans_the_observable_band_in_ascending_order() -> None:
    axis = frequency_axis_hz(CENTER_HZ, SAMPLE_RATE_HZ, FFT_SIZE)

    assert axis.shape == (FFT_SIZE,)
    assert np.all(np.diff(axis) > 0.0)
    bin_hz = SAMPLE_RATE_HZ / FFT_SIZE
    assert axis[0] == pytest.approx(CENTER_HZ - SAMPLE_RATE_HZ / 2.0)
    assert axis[-1] == pytest.approx(CENTER_HZ + SAMPLE_RATE_HZ / 2.0 - bin_hz)


def test_center_bin_holds_the_center_frequency() -> None:
    axis = frequency_axis_hz(CENTER_HZ, SAMPLE_RATE_HZ, FFT_SIZE)

    assert axis[FFT_SIZE // 2] == pytest.approx(CENTER_HZ)
    assert bin_to_freq_hz(FFT_SIZE // 2, CENTER_HZ, SAMPLE_RATE_HZ, FFT_SIZE) == pytest.approx(
        CENTER_HZ
    )


def test_bin_and_freq_conversions_round_trip() -> None:
    for bin_index in (0, 1, 300, FFT_SIZE // 2, FFT_SIZE - 1):
        freq_hz = bin_to_freq_hz(bin_index, CENTER_HZ, SAMPLE_RATE_HZ, FFT_SIZE)
        assert freq_to_bin(freq_hz, CENTER_HZ, SAMPLE_RATE_HZ, FFT_SIZE) == bin_index


def test_freq_to_bin_clamps_out_of_band_requests() -> None:
    below = freq_to_bin(CENTER_HZ - SAMPLE_RATE_HZ, CENTER_HZ, SAMPLE_RATE_HZ, FFT_SIZE)
    above = freq_to_bin(CENTER_HZ + SAMPLE_RATE_HZ, CENTER_HZ, SAMPLE_RATE_HZ, FFT_SIZE)

    assert below == 0
    assert above == FFT_SIZE - 1


def test_band_edges_and_clamping() -> None:
    low_hz, high_hz = band_edges_hz(CENTER_HZ, SAMPLE_RATE_HZ)

    assert low_hz == pytest.approx(CENTER_HZ - 1_024_000.0)
    assert high_hz == pytest.approx(CENTER_HZ + 1_024_000.0)
    assert clamp_freq_to_band(0.0, CENTER_HZ, SAMPLE_RATE_HZ) == pytest.approx(low_hz)
    assert clamp_freq_to_band(1e12, CENTER_HZ, SAMPLE_RATE_HZ) == pytest.approx(high_hz)
    assert clamp_freq_to_band(CENTER_HZ, CENTER_HZ, SAMPLE_RATE_HZ) == pytest.approx(CENTER_HZ)


@pytest.mark.parametrize(
    ("sample_rate_hz", "fft_size"),
    [(0.0, FFT_SIZE), (-1.0, FFT_SIZE), (SAMPLE_RATE_HZ, 0), (SAMPLE_RATE_HZ, -8)],
)
def test_invalid_tuning_raises(sample_rate_hz: float, fft_size: int) -> None:
    with pytest.raises(ValueError):
        frequency_axis_hz(CENTER_HZ, sample_rate_hz, fft_size)
