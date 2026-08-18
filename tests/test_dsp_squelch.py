"""Unit tests for IF channel squelch (ADIM A6)."""

from __future__ import annotations

import numpy as np
import pytest

from sdr_console.dsp.squelch import ChannelSquelch, channel_power_db


def test_channel_power_db_of_unit_tone_is_near_zero() -> None:
    tone = np.exp(1j * np.linspace(0.0, 20.0, 2048)).astype(np.complex64)
    assert channel_power_db(tone) == pytest.approx(0.0, abs=0.05)


def test_channel_power_db_scales_with_amplitude() -> None:
    quiet = 0.1 * np.ones(1024, dtype=np.complex64)
    loud = 1.0 * np.ones(1024, dtype=np.complex64)
    assert channel_power_db(loud) - channel_power_db(quiet) == pytest.approx(20.0, abs=0.05)


def test_squelch_opens_above_threshold_and_closes_with_hysteresis() -> None:
    sql = ChannelSquelch(
        open_threshold_db=-40.0,
        hysteresis_db=6.0,
        hang_s=0.0,
        enabled=True,
    )
    # Below open: stays closed.
    assert sql.update(-50.0, 0.01) is False
    assert sql.is_open is False
    # Cross open threshold.
    assert sql.update(-39.0, 0.01) is True
    assert sql.is_open is True
    # Between close (-46) and open (-40): stay open.
    assert sql.update(-43.0, 0.01) is True
    # Drop below close: close immediately (hang=0).
    assert sql.update(-50.0, 0.01) is False
    assert sql.is_open is False


def test_squelch_hang_delays_close() -> None:
    sql = ChannelSquelch(
        open_threshold_db=-40.0,
        hysteresis_db=3.0,
        hang_s=0.20,
        enabled=True,
    )
    assert sql.update(-30.0, 0.05) is True
    # Below close for less than hang — still open.
    assert sql.update(-60.0, 0.10) is True
    # Remaining hang expires on this block → close.
    assert sql.update(-60.0, 0.15) is False


def test_squelch_disabled_always_open() -> None:
    sql = ChannelSquelch(open_threshold_db=-10.0, enabled=False)
    assert sql.update(-100.0, 0.01) is True
    assert sql.is_open is True


def test_squelch_configure_updates_thresholds() -> None:
    sql = ChannelSquelch(open_threshold_db=-50.0, hysteresis_db=2.0)
    sql.configure(open_threshold_db=-30.0, hysteresis_db=5.0)
    assert sql.open_threshold_db == -30.0
    assert sql.close_threshold_db == -35.0
