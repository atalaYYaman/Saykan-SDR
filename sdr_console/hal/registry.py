"""Device registry — factory and UI-facing device choices."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sdr_console.hal.hackrf_device import HackRfDevice
from sdr_console.hal.interface import SDRDeviceInterface
from sdr_console.hal.mock_device import MockSDRDevice
from sdr_console.hal.pluto_device import PlutoSDRDevice
from sdr_console.hal.rtlsdr_device import RtlSdrDevice

MOCK_DEVICE_ID = "mock"
MOCK_DEVICE_LABEL = "Mock Device"
PLUTO_DEVICE_ID = "pluto"
PLUTO_DEVICE_LABEL = "ADALM-Pluto"
RTLSDR_DEVICE_ID = "rtlsdr"
RTLSDR_DEVICE_LABEL = "RTL-SDR"
HACKRF_DEVICE_ID = "hackrf"
HACKRF_DEVICE_LABEL = "HackRF One"

DeviceFactory = Callable[..., SDRDeviceInterface]
AvailabilityCheck = Callable[[], tuple[bool, str]]


@dataclass(frozen=True)
class DeviceSpec:
    """Registration entry for a device driver."""

    device_id: str
    label: str
    factory: DeviceFactory
    availability: AvailabilityCheck


def _mock_available() -> tuple[bool, str]:
    return True, ""


def _pluto_available() -> tuple[bool, str]:
    try:
        import adi  # noqa: F401  # type: ignore[import-untyped]
    except ImportError:
        return False, "pyadi-iio not installed (pip install -e \".[pluto]\")"
    return True, ""


def _rtlsdr_available() -> tuple[bool, str]:
    try:
        import rtlsdr  # noqa: F401  # type: ignore[import-untyped]
    except ImportError:
        return False, "pyrtlsdr not installed (skeleton driver)"
    return False, "RTL-SDR streaming not implemented yet"


def _hackrf_available() -> tuple[bool, str]:
    for name in ("python_hackrf", "pyhackrf2", "hackrf"):
        try:
            __import__(name)
            return False, "HackRF streaming not implemented yet"
        except ImportError:
            continue
    return False, "HackRF bindings not installed (skeleton driver)"


_DEVICE_SPECS: tuple[DeviceSpec, ...] = (
    DeviceSpec(MOCK_DEVICE_ID, MOCK_DEVICE_LABEL, MockSDRDevice, _mock_available),
    DeviceSpec(PLUTO_DEVICE_ID, PLUTO_DEVICE_LABEL, PlutoSDRDevice, _pluto_available),
    DeviceSpec(RTLSDR_DEVICE_ID, RTLSDR_DEVICE_LABEL, RtlSdrDevice, _rtlsdr_available),
    DeviceSpec(HACKRF_DEVICE_ID, HACKRF_DEVICE_LABEL, HackRfDevice, _hackrf_available),
)

_SPECS_BY_ID: dict[str, DeviceSpec] = {spec.device_id: spec for spec in _DEVICE_SPECS}

DEVICE_CHOICES: tuple[tuple[str, str], ...] = tuple(
    (spec.device_id, spec.label) for spec in _DEVICE_SPECS
)

KNOWN_DEVICE_IDS: frozenset[str] = frozenset(_SPECS_BY_ID)


def is_known_device_id(device_id: str) -> bool:
    return device_id in KNOWN_DEVICE_IDS


def device_availability(device_id: str) -> tuple[bool, str]:
    """Return ``(usable, reason)`` for UI enable/disable of a device entry."""
    spec = _SPECS_BY_ID.get(device_id)
    if spec is None:
        return False, f"Unknown device id: {device_id}"
    return spec.availability()


def create_device(device_id: str, **kwargs: Any) -> SDRDeviceInterface:
    """Create an SDR device instance for ``device_id``.

    Raises:
        ValueError: When ``device_id`` is not registered.
    """
    spec = _SPECS_BY_ID.get(device_id)
    if spec is None:
        raise ValueError(f"Unsupported device id: {device_id}")
    return spec.factory(**kwargs)
