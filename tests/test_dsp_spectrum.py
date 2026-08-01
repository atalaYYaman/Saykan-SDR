"""Unit tests for spectrum processing."""

import numpy as np
import pytest

from sdr_console.dsp.frame import SpectrumFrame
from sdr_console.dsp.spectrum import (
    apply_window,
    compute_fft,
    compute_spectrum_frame,
    compute_waterfall_row,
    to_db,
)


def _make_tone_iq(fft_size: int, sample_rate: float, tone_hz: float) -> np.ndarray:
    sample_indices = np.arange(fft_size, dtype=np.float64)
    phase = 2.0 * np.pi * tone_hz * sample_indices / sample_rate
    return np.exp(1j * phase).astype(np.complex64)


def _expected_peak_bin(fft_size: int, sample_rate: float, tone_hz: float) -> int:
    bin_hz = sample_rate / fft_size
    return fft_size // 2 + int(round(tone_hz / bin_hz))


def test_apply_window_preserves_shape_and_scales_edges() -> None:
    iq = np.ones(1024, dtype=np.complex64)
    windowed = apply_window(iq, window="hann")

    assert windowed.shape == iq.shape
    assert windowed.dtype == np.complex64
    assert float(np.abs(windowed[0])) < 0.01
    assert float(np.abs(windowed[len(windowed) // 2])) > 0.9


def test_apply_window_rejects_empty_input() -> None:
    with pytest.raises(ValueError):
        apply_window(np.array([], dtype=np.complex64))


def test_compute_fft_peak_bin_for_known_tone() -> None:
    fft_size = 1024
    sample_rate = 2_048_000.0
    tone_hz = 50_000.0
    iq = _make_tone_iq(fft_size, sample_rate, tone_hz)

    spectrum = compute_fft(iq, fft_size)

    assert spectrum.shape == (fft_size,)
    assert np.iscomplexobj(spectrum)
    peak_bin = int(np.argmax(np.abs(spectrum)))
    assert peak_bin == _expected_peak_bin(fft_size, sample_rate, tone_hz)


def test_compute_fft_pads_short_input() -> None:
    iq = _make_tone_iq(128, 2_048_000.0, 10_000.0)
    spectrum = compute_fft(iq, fft_size=1024)

    assert spectrum.shape == (1024,)


def test_to_db_zero_division_protection() -> None:
    values = np.array([0.0, 1.0, 10.0], dtype=np.float64)
    db = to_db(values, ref=1.0)

    assert db.shape == values.shape
    assert db.dtype == np.float64
    assert np.isfinite(db[0])
    assert db[0] == pytest.approx(20.0 * np.log10(1e-12))
    assert db[1] == pytest.approx(0.0)
    assert db[2] == pytest.approx(20.0)


def test_to_db_accepts_complex_spectrum() -> None:
    spectrum = np.array([0.0 + 0.0j, 3.0 + 4.0j], dtype=np.complex128)
    db = to_db(spectrum, ref=1.0)

    assert db[0] == pytest.approx(20.0 * np.log10(1e-12))
    assert db[1] == pytest.approx(20.0 * np.log10(5.0))


def test_to_db_rejects_non_positive_reference() -> None:
    with pytest.raises(ValueError):
        to_db(np.array([1.0]), ref=0.0)


def test_spectrum_frame_carries_metadata() -> None:
    fft_size = 1024
    sample_rate = 2_048_000.0
    center_freq = 100_000_000.0
    timestamp = 1_700_000_000.0
    iq = _make_tone_iq(fft_size, sample_rate, 75_000.0)

    frame = compute_spectrum_frame(
        iq,
        fft_size=fft_size,
        center_freq=center_freq,
        sample_rate=sample_rate,
        timestamp=timestamp,
    )

    assert isinstance(frame, SpectrumFrame)
    assert frame.db_values.shape == (fft_size,)
    assert frame.center_freq == center_freq
    assert frame.sample_rate == sample_rate
    assert frame.timestamp == timestamp


def test_compute_spectrum_frame_peak_bin_for_known_tone() -> None:
    fft_size = 1024
    sample_rate = 2_048_000.0
    tone_hz = 50_000.0
    iq = _make_tone_iq(fft_size, sample_rate, tone_hz)

    frame = compute_spectrum_frame(
        iq,
        fft_size=fft_size,
        center_freq=100_000_000.0,
        sample_rate=sample_rate,
    )

    peak_bin = int(np.argmax(frame.db_values))
    assert peak_bin == _expected_peak_bin(fft_size, sample_rate, tone_hz)


def test_compute_waterfall_row_matches_frame_db_values() -> None:
    fft_size = 512
    sample_rate = 1_024_000.0
    tone_hz = 25_000.0
    iq = _make_tone_iq(fft_size, sample_rate, tone_hz)

    row = compute_waterfall_row(iq, fft_size)
    frame = compute_spectrum_frame(
        iq,
        fft_size=fft_size,
        center_freq=433_000_000.0,
        sample_rate=sample_rate,
        timestamp=0.0,
    )

    assert row.shape == (fft_size,)
    np.testing.assert_allclose(row, frame.db_values)


def test_full_scale_tone_peaks_near_zero_dbfs() -> None:
    fft_size = 1024
    sample_rate = 2_048_000.0
    iq = _make_tone_iq(fft_size, sample_rate, 50_000.0)

    frame = compute_spectrum_frame(
        iq,
        fft_size=fft_size,
        center_freq=100_000_000.0,
        sample_rate=sample_rate,
        timestamp=0.0,
    )

    peak_db = float(np.max(frame.db_values))
    assert peak_db == pytest.approx(0.0, abs=0.5)
    assert not frame.db_values.flags.writeable


def test_noise_floor_is_well_below_full_scale() -> None:
    fft_size = 1024
    rng = np.random.default_rng(0)
    iq = (0.01 * (rng.standard_normal(fft_size) + 1j * rng.standard_normal(fft_size))).astype(
        np.complex64
    )
    frame = compute_spectrum_frame(
        iq,
        fft_size=fft_size,
        center_freq=100_000_000.0,
        sample_rate=2_048_000.0,
        timestamp=0.0,
    )
    assert float(np.max(frame.db_values)) < -20.0
