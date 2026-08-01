"""Tests for demodulator mode registry."""

from __future__ import annotations

import pytest

from sdr_console.demod.am import AMDemodulator
from sdr_console.demod.cw import CWDemodulator
from sdr_console.demod.factory import (
    DEMOD_MODES,
    create_demodulator,
    default_bandwidth_hz,
    demodulator_class,
    demodulator_factory,
    is_known_demod_mode,
)
from sdr_console.demod.fm import NFMDemodulator, WFMDemodulator
from sdr_console.demod.ssb import LSBDemodulator, USBDemodulator


def test_all_modes_are_registered() -> None:
    assert DEMOD_MODES == ("AM", "N-FM", "W-FM", "USB", "LSB", "CW")
    for mode in DEMOD_MODES:
        assert is_known_demod_mode(mode)


@pytest.mark.parametrize(
    ("mode", "cls", "bandwidth_hz"),
    [
        ("AM", AMDemodulator, 10_000.0),
        ("N-FM", NFMDemodulator, 12_500.0),
        ("W-FM", WFMDemodulator, 200_000.0),
        ("USB", USBDemodulator, 2_700.0),
        ("LSB", LSBDemodulator, 2_700.0),
        ("CW", CWDemodulator, 500.0),
    ],
)
def test_create_demodulator_builds_the_expected_class(
    mode: str,
    cls,
    bandwidth_hz: float,
) -> None:
    demodulator = create_demodulator(mode, input_rate_hz=48_000.0, audio_decimation=1)

    assert isinstance(demodulator, cls)
    assert demodulator.mode == mode
    assert default_bandwidth_hz(mode) == bandwidth_hz


def test_demodulator_factory_matches_create_demodulator() -> None:
    factory = demodulator_factory("USB")
    demodulator = factory(50_000.0, 2)

    assert isinstance(demodulator, USBDemodulator)
    assert demodulator.input_rate_hz == 50_000.0
    assert demodulator.decimation == 2


def test_unknown_mode_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported demod mode"):
        demodulator_class("SSB")
