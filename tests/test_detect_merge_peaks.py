"""Unit tests for nearby-peak merging."""

from __future__ import annotations

import pytest

from sdr_console.detect.peaks import (
    DetectedPeak,
    filter_peaks_to_range,
    merge_nearby_peaks,
)


def _peak(freq_mhz: float, power_db: float) -> DetectedPeak:
    return DetectedPeak(frequency_hz=freq_mhz * 1_000_000.0, power_db=power_db)


def test_merge_nearby_peaks_combines_close_peaks_and_picks_strongest() -> None:
    peaks = [
        _peak(99.040, -28.0),
        _peak(99.050, -18.0),
        _peak(99.060, -24.0),
        _peak(99.070, -30.0),
    ]
    merge_bandwidth_hz = 150_000.0

    merged = merge_nearby_peaks(peaks, merge_bandwidth_hz)

    assert len(merged) == 1
    assert merged[0].frequency_hz == pytest.approx(99.050e6)
    assert merged[0].power_db == pytest.approx(-18.0)
    assert merged[0].occupied_bandwidth_hz == pytest.approx(30_000.0)


def test_merge_nearby_peaks_keeps_distant_peaks_separate() -> None:
    peaks = [
        _peak(99.050, -20.0),
        _peak(99.250, -22.0),
    ]
    merge_bandwidth_hz = 150_000.0

    merged = merge_nearby_peaks(peaks, merge_bandwidth_hz)

    assert len(merged) == 2
    assert merged[0].frequency_hz == pytest.approx(99.050e6)
    assert merged[1].frequency_hz == pytest.approx(99.250e6)
    assert merged[0].occupied_bandwidth_hz == pytest.approx(0.0)
    assert merged[1].occupied_bandwidth_hz == pytest.approx(0.0)


def test_merge_nearby_peaks_does_not_merge_at_exact_bandwidth_boundary() -> None:
    """Spacing equal to merge_bandwidth_hz starts a new cluster (strict <)."""
    merge_bandwidth_hz = 150_000.0
    peaks = [
        _peak(100.000, -20.0),
        _peak(100.150, -21.0),
    ]

    merged = merge_nearby_peaks(peaks, merge_bandwidth_hz)

    assert len(merged) == 2


def test_merge_nearby_peaks_merges_just_inside_bandwidth_boundary() -> None:
    merge_bandwidth_hz = 150_000.0
    peaks = [
        _peak(100.000, -20.0),
        _peak(100.149, -21.0),
    ]

    merged = merge_nearby_peaks(peaks, merge_bandwidth_hz)

    assert len(merged) == 1
    assert merged[0].power_db == pytest.approx(-20.0)
    assert merged[0].occupied_bandwidth_hz == pytest.approx(149_000.0)


def test_merge_nearby_peaks_returns_sorted_by_frequency() -> None:
    peaks = [
        _peak(101.000, -20.0),
        _peak(99.000, -18.0),
        _peak(100.000, -22.0),
    ]

    merged = merge_nearby_peaks(peaks, merge_bandwidth_hz=50_000.0)

    assert [peak.frequency_hz for peak in merged] == sorted(
        peak.frequency_hz for peak in merged
    )


def test_merge_nearby_peaks_rejects_non_positive_bandwidth() -> None:
    with pytest.raises(ValueError, match="merge_bandwidth_hz"):
        merge_nearby_peaks([_peak(100.0, -20.0)], merge_bandwidth_hz=0.0)


def test_merge_nearby_peaks_merges_screenshot_cluster_at_50_khz() -> None:
    peaks = [
        _peak(freq_mhz, -39.0)
        for freq_mhz in (
            98.964,
            98.980,
            98.984,
            99.002,
            99.004,
            99.008,
            99.016,
            99.026,
        )
    ]

    merged = merge_nearby_peaks(peaks, merge_bandwidth_hz=50_000.0)

    assert len(merged) == 1
    assert merged[0].power_db == pytest.approx(-39.0)
    assert merged[0].occupied_bandwidth_hz == pytest.approx(62_000.0, rel=1e-2)


def test_filter_peaks_to_range_keeps_in_band_only() -> None:
    peaks = [
        _peak(98.900, -20.0),
        _peak(99.500, -18.0),
        _peak(100.200, -22.0),
    ]

    filtered = filter_peaks_to_range(peaks, 99_000_000.0, 100_000_000.0)

    assert len(filtered) == 1
    assert filtered[0].frequency_hz == pytest.approx(99_500_000.0)
