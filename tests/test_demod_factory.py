"""Tests for demodulator mode registry."""

from __future__ import annotations

import pytest

from sdr_console.demod.am import AMDemodulator
from sdr_console.demod.cw import CWDemodulator
from sdr_console.demod.factory import (
    DEMOD_MODES,
    DEFAULT_AFBW_HZ,
    DEFAULT_AGC_ENABLED,
    DEFAULT_AGC_PRESET,
    DEFAULT_RFBW_HZ,
    create_demodulator,
    default_afbw_hz,
    default_agc_enabled,
    default_agc_preset,
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
    assert DEFAULT_RFBW_HZ[mode] == bandwidth_hz


def test_default_rfbw_table_covers_every_registered_mode() -> None:
    assert set(DEFAULT_RFBW_HZ) == set(DEMOD_MODES)
    assert DEFAULT_RFBW_HZ["AM"] == 10_000.0
    assert DEFAULT_RFBW_HZ["N-FM"] == 12_500.0
    assert DEFAULT_RFBW_HZ["W-FM"] == 200_000.0
    assert DEFAULT_RFBW_HZ["USB"] == 2_700.0
    assert DEFAULT_RFBW_HZ["LSB"] == 2_700.0
    assert DEFAULT_RFBW_HZ["CW"] == 500.0


def test_default_afbw_table_covers_every_registered_mode() -> None:
    assert set(DEFAULT_AFBW_HZ) == set(DEMOD_MODES)
    assert default_afbw_hz("AM") == 4_000.0
    assert default_afbw_hz("N-FM") == 4_000.0
    assert default_afbw_hz("W-FM") == 15_000.0
    assert default_afbw_hz("USB") == 3_000.0
    assert default_afbw_hz("LSB") == 3_000.0
    assert default_afbw_hz("CW") == 1_000.0


def test_default_agc_table_covers_every_registered_mode() -> None:
    assert set(DEFAULT_AGC_ENABLED) == set(DEMOD_MODES)
    assert set(DEFAULT_AGC_PRESET) == set(DEMOD_MODES)
    assert default_agc_enabled("AM") is True
    assert default_agc_preset("AM") == "slow"
    assert default_agc_preset("USB") == "hang"
    assert default_agc_preset("N-FM") == "limiter"
    assert default_agc_preset("W-FM") == "limiter"
    assert default_agc_preset("CW") == "fast"


def test_demodulator_factory_matches_create_demodulator() -> None:
    factory = demodulator_factory("USB")
    demodulator = factory(50_000.0, 2)

    assert isinstance(demodulator, USBDemodulator)
    assert demodulator.input_rate_hz == 50_000.0
    assert demodulator.decimation == 2


def test_unknown_mode_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported demod mode"):
        demodulator_class("SSB")
