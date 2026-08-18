"""Automatic signal detection on processed spectrum frames."""

from sdr_console.detect.detected_signal import DetectedSignal
from sdr_console.detect.identified import IdentifiedPeak
from sdr_console.detect.peaks import (
    DEFAULT_MERGE_BANDWIDTH_HZ,
    MAX_MERGE_DISTANCE_HZ,
    MIN_MERGE_DISTANCE_HZ,
    DetectedPeak,
    default_merge_distance_hz_for_mode,
    detect_peaks,
    filter_peaks_to_range,
    merge_nearby_peaks,
)
from sdr_console.detect.station_db import (
    DEFAULT_STATION_DB_PATH,
    DEFAULT_STATION_MATCH_TOLERANCE_HZ,
    StationDatabase,
)
from sdr_console.detect.tracker import SignalTracker

__all__ = [
    "DEFAULT_MERGE_BANDWIDTH_HZ",
    "MAX_MERGE_DISTANCE_HZ",
    "MIN_MERGE_DISTANCE_HZ",
    "DEFAULT_STATION_DB_PATH",
    "DEFAULT_STATION_MATCH_TOLERANCE_HZ",
    "DetectedPeak",
    "DetectedSignal",
    "IdentifiedPeak",
    "SignalTracker",
    "StationDatabase",
    "detect_peaks",
    "default_merge_distance_hz_for_mode",
    "filter_peaks_to_range",
    "merge_nearby_peaks",
]
