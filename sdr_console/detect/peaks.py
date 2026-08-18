"""Peak detection on ``SpectrumFrame`` rows."""

from __future__ import annotations

from dataclasses import dataclass

from scipy.signal import find_peaks

from sdr_console.dsp.axis import bin_to_freq_hz
from sdr_console.dsp.frame import SpectrumFrame


DEFAULT_MERGE_BANDWIDTH_HZ = 100_000.0
MIN_MERGE_DISTANCE_HZ = 50_000.0
MAX_MERGE_DISTANCE_HZ = 200_000.0
MERGE_DISTANCE_PRESETS_HZ: tuple[float, ...] = (
    50_000.0,
    75_000.0,
    100_000.0,
    150_000.0,
    200_000.0,
)

_MODE_DEFAULT_MERGE_DISTANCE_HZ: dict[str, float] = {
    "W-FM": 200_000.0,
    "N-FM": 25_000.0,
    "AM": 50_000.0,
    "USB": 10_000.0,
    "LSB": 10_000.0,
    "CW": 5_000.0,
}


def clamp_merge_distance_hz(merge_distance_hz: float) -> float:
    """Clamp a merge distance to the supported broadcast-oriented range."""
    return min(max(float(merge_distance_hz), MIN_MERGE_DISTANCE_HZ), MAX_MERGE_DISTANCE_HZ)


def default_merge_distance_hz_for_mode(mode: str) -> float:
    """Suggested merge distance when the user picks a demod mode."""
    preset = _MODE_DEFAULT_MERGE_DISTANCE_HZ.get(mode)
    if preset is not None:
        return clamp_merge_distance_hz(preset)
    from sdr_console.demod.factory import default_bandwidth_hz

    return clamp_merge_distance_hz(default_bandwidth_hz(mode))


@dataclass(frozen=True, slots=True)
class DetectedPeak:
    """One signal peak above the detection threshold."""

    frequency_hz: float
    power_db: float
    occupied_bandwidth_hz: float = 0.0


def detect_peaks(
    spectrum_frame: SpectrumFrame,
    threshold_db: float,
    min_distance_hz: float,
) -> list[DetectedPeak]:
    """Detect spectral peaks above ``threshold_db`` with minimum spacing.

    Args:
        spectrum_frame: Processed spectrum row from the DSP pipeline.
        threshold_db: Minimum dBFS value for a bin to qualify as a peak.
        min_distance_hz: Minimum frequency spacing between detected peaks.

    Returns:
        Peaks sorted by ascending frequency.
    """
    if min_distance_hz < 0.0:
        raise ValueError("min_distance_hz must be non-negative")

    db_values = spectrum_frame.db_values
    fft_size = int(db_values.size)
    if fft_size == 0:
        return []

    sample_rate_hz = spectrum_frame.sample_rate
    if sample_rate_hz <= 0.0:
        raise ValueError("sample_rate must be positive")

    bin_width_hz = sample_rate_hz / fft_size
    if min_distance_hz > 0.0:
        min_distance_bins = max(1, int(round(min_distance_hz / bin_width_hz)))
    else:
        min_distance_bins = 1

    indices, properties = find_peaks(
        db_values,
        height=threshold_db,
        distance=min_distance_bins,
    )
    heights = properties["peak_heights"]

    peaks: list[DetectedPeak] = []
    for bin_index, power_db in zip(indices, heights, strict=True):
        frequency_hz = bin_to_freq_hz(
            int(bin_index),
            spectrum_frame.center_freq,
            sample_rate_hz,
            fft_size,
        )
        peaks.append(DetectedPeak(frequency_hz=frequency_hz, power_db=float(power_db)))

    return peaks


def merge_nearby_peaks(
    peaks: list[DetectedPeak],
    merge_bandwidth_hz: float,
) -> list[DetectedPeak]:
    """Merge peaks whose frequencies are within ``merge_bandwidth_hz`` of each other.

    Uses single-linkage clustering on sorted frequencies: peaks belong to the
    same cluster when the gap to the previous cluster member is strictly less
    than ``merge_bandwidth_hz``. Each cluster is represented by its strongest
    peak (highest ``power_db``).
    """
    if merge_bandwidth_hz <= 0.0:
        raise ValueError("merge_bandwidth_hz must be positive")
    if not peaks:
        return []

    sorted_peaks = sorted(peaks, key=lambda peak: peak.frequency_hz)
    clusters: list[list[DetectedPeak]] = [[sorted_peaks[0]]]

    for peak in sorted_peaks[1:]:
        cluster_end_hz = max(item.frequency_hz for item in clusters[-1])
        if peak.frequency_hz - cluster_end_hz < merge_bandwidth_hz:
            clusters[-1].append(peak)
        else:
            clusters.append([peak])

    merged: list[DetectedPeak] = []
    for cluster in clusters:
        strongest = max(cluster, key=lambda item: item.power_db)
        frequencies_hz = [item.frequency_hz for item in cluster]
        occupied_bandwidth_hz = max(frequencies_hz) - min(frequencies_hz)
        merged.append(
            DetectedPeak(
                frequency_hz=strongest.frequency_hz,
                power_db=strongest.power_db,
                occupied_bandwidth_hz=occupied_bandwidth_hz,
            )
        )

    return merged


def filter_peaks_to_range(
    peaks: list[DetectedPeak],
    start_freq_hz: float,
    end_freq_hz: float,
) -> list[DetectedPeak]:
    """Keep only peaks whose frequency lies inside the inclusive scan band."""
    if start_freq_hz > end_freq_hz:
        start_freq_hz, end_freq_hz = end_freq_hz, start_freq_hz
    return [
        peak
        for peak in peaks
        if start_freq_hz <= peak.frequency_hz <= end_freq_hz
    ]
