"""Unit tests for the user-editable station database."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdr_console.detect.peaks import DetectedPeak
from sdr_console.detect.station_db import StationDatabase, parse_station_entries


def test_parse_frequency_map_entries() -> None:
    raw = {
        "97000000": "TRT FM",
        "100700000": "TRT Radyo 1",
    }

    entries = parse_station_entries(raw)

    assert entries == [
        (97_000_000.0, "TRT FM"),
        (100_700_000.0, "TRT Radyo 1"),
    ]


def test_parse_station_list_with_mhz_entries() -> None:
    raw = {
        "stations": [
            {"frequency_mhz": 101.5, "name": "Power FM"},
            {"frequency_hz": 88_500_000, "name": "Classic"},
        ]
    }

    entries = parse_station_entries(raw)

    assert (101_500_000.0, "Power FM") in entries
    assert (88_500_000.0, "Classic") in entries


def test_load_missing_file_returns_empty_database(tmp_path: Path) -> None:
    database = StationDatabase.load(tmp_path / "missing.json")

    assert database.entries == ()


def test_load_fixture_database(fixtures_dir: Path) -> None:
    database = StationDatabase.load(fixtures_dir / "stations.json")

    assert database.lookup(97_000_000.0, tolerance_hz=1_000.0) == "TRT FM"
    assert database.lookup(101_500_000.0, tolerance_hz=1_000.0) == "Power FM"


def test_lookup_returns_none_outside_tolerance() -> None:
    database = StationDatabase([(97_000_000.0, "TRT FM")])

    assert database.lookup(97_010_000.0, tolerance_hz=5_000.0) is None


def test_lookup_prefers_closest_station() -> None:
    database = StationDatabase(
        [
            (97_000_000.0, "Far"),
            (97_003_000.0, "Near"),
        ]
    )

    assert database.lookup(97_002_500.0, tolerance_hz=10_000.0) == "Near"


def test_annotate_peaks_adds_names_when_matched() -> None:
    database = StationDatabase([(100_700_000.0, "TRT Radyo 1")])
    peaks = [
        DetectedPeak(frequency_hz=100_700_500.0, power_db=-18.0),
        DetectedPeak(frequency_hz=95_000_000.0, power_db=-30.0),
    ]

    identified = database.annotate_peaks(peaks, tolerance_hz=5_000.0)

    assert identified[0].name == "TRT Radyo 1"
    assert identified[1].name is None


def test_load_invalid_json_returns_empty_database(tmp_path: Path) -> None:
    path = tmp_path / "stations.json"
    path.write_text("{not json", encoding="utf-8")

    database = StationDatabase.load(path)

    assert database.entries == ()


def test_load_invalid_shape_returns_empty_database(tmp_path: Path) -> None:
    path = tmp_path / "stations.json"
    path.write_text(json.dumps(["only", "strings"]), encoding="utf-8")

    database = StationDatabase.load(path)

    assert database.entries == ()


def test_lookup_rejects_negative_tolerance() -> None:
    database = StationDatabase([(97_000_000.0, "TRT FM")])

    with pytest.raises(ValueError, match="tolerance_hz"):
        database.lookup(97_000_000.0, tolerance_hz=-1.0)
