"""JamSession — Mock TX, jam tabanı, süre dolunca stop."""

from __future__ import annotations

import time

import numpy as np
import pytest

from sdr_console.ea.constants import MIN_JAM_ATTENUATION_DB
from sdr_console.ea.errors import JamNotConfirmedError, JamPolicyError
from sdr_console.ea.session import JamSession
from sdr_console.tx.constants import MIN_TX_ATTENUATION_DB
from sdr_console.tx.errors import TXAttenuationLimitError
from sdr_console.tx.mock_tx import MockTXDevice


def test_session_requires_confirmation() -> None:
    device = MockTXDevice()
    session = JamSession()
    with pytest.raises(JamNotConfirmedError):
        session.start(
            device,
            sample_rate_hz=2_048_000.0,
            freq_hz=433_970_000.0,
            bandwidth_hz=2_048_000.0,
            attenuation_db=MIN_JAM_ATTENUATION_DB,
            duration_s=0.20,
            confirmed=False,
            authorized_window=True,
        )
    assert not session.is_active
    assert not device.is_transmitting


def test_session_accepts_jam_floor_and_stops() -> None:
    device = MockTXDevice()
    session = JamSession()
    iq = session.start(
        device,
        sample_rate_hz=2_048_000.0,
        freq_hz=433_970_000.0,
        bandwidth_hz=500_000.0,
        attenuation_db=MIN_JAM_ATTENUATION_DB,
        duration_s=0.20,
        confirmed=True,
        authorized_window=True,
        rng=np.random.default_rng(0),
    )
    assert session.is_active
    assert device.is_transmitting
    assert device.attenuation_db == pytest.approx(MIN_JAM_ATTENUATION_DB)
    assert device.transmitted_iq is not None
    assert np.array_equal(device.transmitted_iq, iq)
    assert float(np.max(np.abs(iq))) <= 1.0 + 1e-5

    deadline = time.monotonic() + 1.5
    while device.is_transmitting and time.monotonic() < deadline:
        time.sleep(0.02)
    assert not device.is_transmitting
    session.stop()
    assert not session.is_active


def test_default_tx_floor_still_rejects_twenty_db() -> None:
    device = MockTXDevice()
    with pytest.raises(TXAttenuationLimitError):
        device.set_tx_attenuation_db(20.0)
    assert MIN_TX_ATTENUATION_DB == 40.0


def test_session_rejects_duration_above_jam_ceiling() -> None:
    device = MockTXDevice()
    session = JamSession()
    with pytest.raises(JamPolicyError, match="tavan"):
        session.start(
            device,
            sample_rate_hz=2_048_000.0,
            freq_hz=433_970_000.0,
            bandwidth_hz=500_000.0,
            attenuation_db=MIN_JAM_ATTENUATION_DB,
            duration_s=16.0,
            confirmed=True,
            authorized_window=True,
        )
    assert not device.is_transmitting
