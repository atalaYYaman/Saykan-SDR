"""HAL-level exception hierarchy for SDR device drivers."""


class DeviceError(Exception):
    """Base class for hardware abstraction errors."""


class DeviceUnavailableError(DeviceError):
    """Raised when a required driver library or DLL is missing."""


class DeviceConnectionError(DeviceError):
    """Raised when the hardware cannot be opened or the link drops."""
