"""Unit tests for spectrum peak detection."""

from __future__ import annotations

import numpy as np
import pytest

from sdr_console.detect.peaks import DetectedPeak, detect_peaks
from sdr_console.dsp.axis import freq_to_bin
from sdr_console.dsp.frame import SpectrumFrame
from sdr_console.dsp.spectrum import compute_spectrum_frame
from tests.conftest import make_tone_iq


def _synthetic_frame(
    peak_specs: list[tuple[float, float]],
    *,
    fft_size: int = 1024,
    center_freq_hz: float = 100_000_000.0,
    sample_rate_hz: float = 2_048_000.0,
    floor_db: float = -80.0,
) -> SpectrumFrame:
    """Build a spectrum with narrow synthetic peaks on a flat noise floor."""
    db_values = np.full(fft_size, floor_db, dtype=np.float64)
    for freq_hz, power_db in peak_specs:
        bin_index = freq_to_bin(freq_hz, center_freq_hz, sample_rate_hz, fft_size)
        db_values[bin_index] = power_db

    return SpectrumFrame(
        db_values=db_values,
        center_freq=center_freq_hz,
        sample_rate=sample_rate_hz,
        timestamp=0.0,
    )


def test_detect_peaks_finds_synthetic_peaks_at_expected_frequency_and_power() -> None:
    center_hz = 100_000_000.0
    sample_rate_hz = 2_048_000.0
    peak_specs = [
        (99_800_000.0, -25.0),
        (100_050_000.0, -18.0),
        (100_300_000.0, -30.0),
    ]
    frame = _synthetic_frame(peak_specs, center_freq_hz=center_hz, sample_rate_hz=sample_rate_hz)

    peaks = detect_peaks(frame, threshold_db=-40.0, min_distance_hz=50_000.0)

    assert len(peaks) == 3
    for expected_freq_hz, expected_power_db in peak_specs:
        match = next(
            peak
            for peak in peaks
            if abs(peak.frequency_hz - expected_freq_hz) <= sample_rate_hz / frame.db_values.size
        )
        assert match.power_db == pytest.approx(expected_power_db)


def test_detect_peaks_finds_known_fft_tones() -> None:
    fft_size = 1024
    sample_rate_hz = 2_048_000.0
    center_hz = 100_000_000.0
    tone_offsets_hz = (-200_000.0, 50_000.0, 300_000.0)
    iq = sum(make_tone_iq(fft_size, sample_rate_hz, offset_hz) for offset_hz in tone_offsets_hz)
    frame = compute_spectrum_frame(
        iq,
        fft_size=fft_size,
        center_freq=center_hz,
        sample_rate=sample_rate_hz,
        timestamp=0.0,
    )

    peaks = detect_peaks(frame, threshold_db=-20.0, min_distance_hz=50_000.0)

    assert len(peaks) == 3
    expected_freqs_hz = [center_hz + offset_hz for offset_hz in tone_offsets_hz]
    bin_width_hz = sample_rate_hz / fft_size
    for expected_freq_hz in expected_freqs_hz:
        assert any(abs(peak.frequency_hz - expected_freq_hz) <= bin_width_hz for peak in peaks)
        matching = [
            peak for peak in peaks if abs(peak.frequency_hz - expected_freq_hz) <= bin_width_hz
        ]
        assert matching[0].power_db > -10.0


def test_detect_peaks_ignores_noise_floor_ripples() -> None:
    fft_size = 1024
    rng = np.random.default_rng(42)
    db_values = rng.uniform(-78.0, -65.0, size=fft_size).astype(np.float64)
    frame = SpectrumFrame(
        db_values=db_values,
        center_freq=100_000_000.0,
        sample_rate=2_048_000.0,
        timestamp=0.0,
    )

    peaks = detect_peaks(frame, threshold_db=-40.0, min_distance_hz=10_000.0)

    assert peaks == []


def test_detect_peaks_respects_min_distance() -> None:
    center_hz = 100_000_000.0
    sample_rate_hz = 2_048_000.0
    bin_width_hz = sample_rate_hz / 1024
    close_spacing_hz = bin_width_hz * 3
    peak_a_hz = center_hz - 100_000.0
    peak_b_hz = peak_a_hz + close_spacing_hz
    frame = _synthetic_frame(
        [(peak_a_hz, -20.0), (peak_b_hz, -22.0)],
        center_freq_hz=center_hz,
        sample_rate_hz=sample_rate_hz,
    )

    close_peaks = detect_peaks(frame, threshold_db=-40.0, min_distance_hz=0.0)
    distant_peaks = detect_peaks(frame, threshold_db=-40.0, min_distance_hz=100_000.0)

    assert len(close_peaks) == 2
    assert len(distant_peaks) == 1
    assert distant_peaks[0].power_db == pytest.approx(-20.0)


def test_detect_peaks_rejects_negative_min_distance() -> None:
    frame = _synthetic_frame([(100_000_000.0, -20.0)])

    with pytest.raises(ValueError, match="min_distance_hz"):
        detect_peaks(frame, threshold_db=-40.0, min_distance_hz=-1.0)


def test_detect_peaks_returns_detected_peak_instances() -> None:
    frame = _synthetic_frame([(100_050_000.0, -15.0)])

    peaks = detect_peaks(frame, threshold_db=-40.0, min_distance_hz=0.0)

    assert len(peaks) == 1
    assert isinstance(peaks[0], DetectedPeak)
