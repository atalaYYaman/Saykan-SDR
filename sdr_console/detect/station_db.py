"""User-editable JSON station list for naming detected frequencies."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sdr_console.detect.identified import IdentifiedPeak
from sdr_console.detect.peaks import DetectedPeak

logger = logging.getLogger(__name__)

DEFAULT_STATION_DB_PATH = Path.home() / ".sdr-console" / "stations.json"
DEFAULT_STATION_MATCH_TOLERANCE_HZ = 5_000.0


def _normalize_frequency_hz(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{field_name} must be a number")

    frequency_hz = float(str(value).strip())
    if frequency_hz <= 0.0:
        raise ValueError(f"{field_name} must be positive")
    return frequency_hz


def _parse_station_record(record: object) -> tuple[float, str]:
    if not isinstance(record, dict):
        raise ValueError("station entry must be an object")

    name = record.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("station entry requires a non-empty name")

    if "frequency_hz" in record:
        frequency_hz = _normalize_frequency_hz(record["frequency_hz"], field_name="frequency_hz")
    elif "frequency_mhz" in record:
        frequency_mhz = _normalize_frequency_hz(
            record["frequency_mhz"],
            field_name="frequency_mhz",
        )
        frequency_hz = frequency_mhz * 1_000_000.0
    else:
        raise ValueError("station entry requires frequency_hz or frequency_mhz")

    return frequency_hz, name.strip()


def _parse_station_list(records: object) -> list[tuple[float, str]]:
    if not isinstance(records, list):
        raise ValueError("station list must be an array")

    return [_parse_station_record(record) for record in records]


def _parse_frequency_map(mapping: dict[object, object]) -> list[tuple[float, str]]:
    entries: list[tuple[float, str]] = []
    for raw_frequency, raw_name in mapping.items():
        if raw_frequency == "stations":
            continue
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise ValueError("station names must be non-empty strings")
        frequency_hz = _normalize_frequency_hz(raw_frequency, field_name="frequency")
        entries.append((frequency_hz, raw_name.strip()))
    return entries


def parse_station_entries(raw: object) -> list[tuple[float, str]]:
    """Parse supported JSON shapes into ``(frequency_hz, name)`` rows."""
    if isinstance(raw, list):
        return _parse_station_list(raw)

    if isinstance(raw, dict):
        if "stations" in raw:
            stations = _parse_station_list(raw["stations"])
            extra = _parse_frequency_map(
                {key: value for key, value in raw.items() if key != "stations"}
            )
            return stations + extra
        return _parse_frequency_map(raw)

    raise ValueError("station database must be a JSON object or array")


class StationDatabase:
    """Lookup table loaded from a user-maintained JSON file."""

    def __init__(self, entries: list[tuple[float, str]] | None = None) -> None:
        self._entries = sorted(entries or [], key=lambda item: item[0])

    @property
    def entries(self) -> tuple[tuple[float, str], ...]:
        return tuple(self._entries)

    @classmethod
    def load(cls, path: Path | None = None) -> StationDatabase:
        """Load stations from ``path``; missing files yield an empty database."""
        db_path = path or DEFAULT_STATION_DB_PATH
        if not db_path.exists():
            return cls([])

        try:
            raw = json.loads(db_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load station database from %s (%s)", db_path, exc)
            return cls([])

        try:
            entries = parse_station_entries(raw)
        except ValueError as exc:
            logger.warning("Invalid station database %s (%s)", db_path, exc)
            return cls([])

        return cls(entries)

    def lookup(self, frequency_hz: float, tolerance_hz: float) -> str | None:
        """Return the closest station name within ``tolerance_hz``, if any."""
        if tolerance_hz < 0.0:
            raise ValueError("tolerance_hz must be non-negative")

        best_name: str | None = None
        best_distance_hz = float("inf")

        for station_freq_hz, station_name in self._entries:
            distance_hz = abs(station_freq_hz - frequency_hz)
            if distance_hz <= tolerance_hz and distance_hz < best_distance_hz:
                best_distance_hz = distance_hz
                best_name = station_name

        return best_name

    def annotate_peaks(
        self,
        peaks: list[DetectedPeak],
        tolerance_hz: float = DEFAULT_STATION_MATCH_TOLERANCE_HZ,
    ) -> list[IdentifiedPeak]:
        """Attach station names to detected peaks when frequencies match."""
        return [
            IdentifiedPeak.from_peak(
                peak,
                name=self.lookup(peak.frequency_hz, tolerance_hz),
            )
            for peak in peaks
        ]
