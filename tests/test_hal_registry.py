"""Unit tests for the HAL device registry."""

import pytest

from sdr_console.hal.interface import SDRDeviceInterface
from sdr_console.hal.registry import (
    DEVICE_CHOICES,
    HACKRF_DEVICE_ID,
    KNOWN_DEVICE_IDS,
    MOCK_AM_DEVICE_ID,
    MOCK_DEVICE_ID,
    PLUTO_DEVICE_ID,
    RTLSDR_DEVICE_ID,
    create_device,
    device_availability,
    is_known_device_id,
    static_capabilities,
)
from sdr_console.hal.scenarios import AMMockDevice
from sdr_console.hal.mock_device import MOCK_CAPABILITIES
from sdr_console.hal.pluto_device import PLUTO_CAPABILITIES


def test_known_device_ids_include_hardware_entries() -> None:
    assert MOCK_DEVICE_ID in KNOWN_DEVICE_IDS
    assert MOCK_AM_DEVICE_ID in KNOWN_DEVICE_IDS
    assert PLUTO_DEVICE_ID in KNOWN_DEVICE_IDS
    assert RTLSDR_DEVICE_ID in KNOWN_DEVICE_IDS
    assert HACKRF_DEVICE_ID in KNOWN_DEVICE_IDS
    assert is_known_device_id(PLUTO_DEVICE_ID)
    assert not is_known_device_id("nope")


def test_static_capabilities_cover_registered_devices() -> None:
    assert static_capabilities(MOCK_DEVICE_ID) is MOCK_CAPABILITIES
    assert static_capabilities(MOCK_AM_DEVICE_ID) is MOCK_CAPABILITIES
    assert static_capabilities(PLUTO_DEVICE_ID) is PLUTO_CAPABILITIES
    assert static_capabilities("nope") is None


def test_device_choices_labels() -> None:
    ids = [device_id for device_id, _ in DEVICE_CHOICES]
    assert ids == [
        MOCK_DEVICE_ID,
        MOCK_AM_DEVICE_ID,
        PLUTO_DEVICE_ID,
        RTLSDR_DEVICE_ID,
        HACKRF_DEVICE_ID,
    ]


def test_create_am_mock_device_carries_the_test_transmitter() -> None:
    device = create_device(
        MOCK_AM_DEVICE_ID,
        sample_rate_hz=2_048_000.0,
        center_freq_hz=100_000_000.0,
        gain_db=40.0,
        noise_amplitude=0.01,
        realtime=False,
    )

    assert isinstance(device, AMMockDevice)
    assert device.am.carrier_freq_hz == 100_050_000.0
    assert device.gain_db == 40.0
    assert device.capabilities is not None


def test_create_device_mock_and_pluto() -> None:
    mock = create_device(MOCK_DEVICE_ID, realtime=False)
    assert isinstance(mock, SDRDeviceInterface)

    pluto = create_device(
        PLUTO_DEVICE_ID,
        sample_rate_hz=2_048_000.0,
        center_freq_hz=100_000_000.0,
        gain_db=40.0,
    )
    assert isinstance(pluto, SDRDeviceInterface)


def test_create_device_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported device"):
        create_device("does-not-exist")


def test_device_availability_mock_always_true() -> None:
    ok, reason = device_availability(MOCK_DEVICE_ID)
    assert ok is True
    assert reason == ""


def test_device_availability_unknown() -> None:
    ok, reason = device_availability("nope")
    assert ok is False
    assert "Unknown" in reason
