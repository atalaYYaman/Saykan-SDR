"""Detected peaks optionally matched to known station names."""

from __future__ import annotations

from dataclasses import dataclass

from sdr_console.detect.detected_signal import DetectedSignal
from sdr_console.detect.peaks import DetectedPeak


@dataclass(frozen=True, slots=True)
class IdentifiedPeak:
    """One confirmed detection, with optional station-database metadata."""

    frequency_hz: float
    power_db: float
    capture_gain_db: float = 0.0
    detection_count: int = 1
    confirmed_at: int = 0
    name: str | None = None

    @classmethod
    def from_peak(cls, peak: DetectedPeak, name: str | None = None) -> IdentifiedPeak:
        return cls(
            frequency_hz=peak.frequency_hz,
            power_db=peak.power_db,
            name=name,
        )

    @classmethod
    def from_signal(
        cls,
        signal: DetectedSignal,
        *,
        name: str | None = None,
    ) -> IdentifiedPeak:
        return cls(
            frequency_hz=signal.frequency_hz,
            power_db=signal.power_db,
            capture_gain_db=signal.capture_gain_db,
            detection_count=signal.detection_count,
            confirmed_at=signal.confirmed_at,
            name=name if name is not None else signal.name,
        )
