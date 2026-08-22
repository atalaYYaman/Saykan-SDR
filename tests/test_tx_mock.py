"""MockTXDevice güvenlik ve süre sınırı testleri."""

from __future__ import annotations

import time

import numpy as np
import pytest

from sdr_console.tx.constants import DEFAULT_TX_ATTENUATION_DB, MIN_TX_ATTENUATION_DB
from sdr_console.tx.errors import TXAttenuationLimitError
from sdr_console.tx.mock_tx import MockTXDevice


def _tone_iq(num_samples: int = 4096) -> np.ndarray:
    phase = np.linspace(0, 8 * np.pi, num_samples, endpoint=False)
    return np.exp(1j * phase).astype(np.complex64)


def test_default_attenuation_is_minus_40_db() -> None:
    device = MockTXDevice()
    assert device.attenuation_db == DEFAULT_TX_ATTENUATION_DB
    assert DEFAULT_TX_ATTENUATION_DB == 40.0


def test_attenuation_limit_rejects_too_strong_tx() -> None:
    device = MockTXDevice()
    with pytest.raises(TXAttenuationLimitError, match="güvenlik"):
        device.set_tx_attenuation_db(MIN_TX_ATTENUATION_DB - 1.0)


def test_transmit_records_iq_and_stops_after_max_duration() -> None:
    device = MockTXDevice()
    iq = _tone_iq(1024)
    device.transmit(iq, cyclic=True, max_duration_s=0.15)

    assert device.is_transmitting
    assert device.transmitted_iq is not None
    assert np.array_equal(device.transmitted_iq, iq)

    deadline = time.monotonic() + 1.0
    while device.is_transmitting and time.monotonic() < deadline:
        time.sleep(0.02)

    assert not device.is_transmitting


def test_none_max_duration_uses_default_and_stops() -> None:
    device = MockTXDevice()
    device.transmit(_tone_iq(256), cyclic=False, max_duration_s=None)
    assert device.is_transmitting
    device.stop_tx()
    assert not device.is_transmitting


def test_constructor_rejects_attenuation_below_limit() -> None:
    with pytest.raises(TXAttenuationLimitError):
        MockTXDevice(attenuation_db=20.0)


def test_jam_floor_allows_ten_db() -> None:
    from sdr_console.tx.constants import ABSOLUTE_MIN_ATTENUATION_DB

    device = MockTXDevice(
        attenuation_db=ABSOLUTE_MIN_ATTENUATION_DB,
        min_attenuation_db=ABSOLUTE_MIN_ATTENUATION_DB,
    )
    assert device.attenuation_db == pytest.approx(ABSOLUTE_MIN_ATTENUATION_DB)
    device.set_tx_attenuation_db(15.0)
    assert device.attenuation_db == pytest.approx(15.0)


def test_floor_cannot_go_below_absolute_minimum() -> None:
    device = MockTXDevice()
    with pytest.raises(TXAttenuationLimitError):
        device.set_min_attenuation_db(9.0)


def test_set_tx_bandwidth_is_stored() -> None:
    device = MockTXDevice()
    device.set_tx_bandwidth_hz(25_000.0)
    assert device.bandwidth_hz == pytest.approx(25_000.0)
