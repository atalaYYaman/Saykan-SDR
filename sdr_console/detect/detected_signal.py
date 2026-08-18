"""Confirmed signal entries exposed by the detection tracker."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DetectedSignal:
    """One confirmed signal retained for the current session."""

    frequency_hz: float
    power_db: float
    capture_gain_db: float
    detection_count: int
    confirmed_at: int
    name: str | None = None
