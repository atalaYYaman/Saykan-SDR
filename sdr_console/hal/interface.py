"""Abstract interface for all SDR hardware drivers."""

from abc import ABC, abstractmethod

import numpy as np

from sdr_console.hal.capabilities import DeviceCapabilities


class SDRDeviceInterface(ABC):
    """Common contract implemented by real devices and mock sources."""

    @property
    @abstractmethod
    def capabilities(self) -> DeviceCapabilities:
        """Return static hardware limits for this device."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Return True when the device is ready to stream."""

    @property
    @abstractmethod
    def center_freq_hz(self) -> float:
        """Current center frequency in Hz."""

    @property
    @abstractmethod
    def sample_rate_hz(self) -> float:
        """Current IQ sample rate in samples per second."""

    @property
    @abstractmethod
    def gain_db(self) -> float:
        """Current receiver gain in dB."""

    @property
    def gain_mode(self) -> str:
        """Current gain control mode (default ``manual``)."""
        return "manual"

    @abstractmethod
    def connect(self) -> None:
        """Open the device and prepare for streaming."""

    @abstractmethod
    def disconnect(self) -> None:
        """Stop streaming and release resources."""

    @abstractmethod
    def set_center_freq(self, freq_hz: float) -> None:
        """Set the receiver center frequency in Hz."""

    @abstractmethod
    def set_sample_rate(self, rate_hz: float) -> None:
        """Set the IQ sample rate in samples per second."""

    @abstractmethod
    def set_gain(self, gain_db: float) -> None:
        """Set receiver gain in dB."""

    def set_gain_mode(self, mode: str) -> None:
        """Set gain control mode.

        Default implementation only accepts ``manual``. Drivers that support
        AGC override this method.
        """
        if mode != "manual":
            raise ValueError(f"Gain mode {mode!r} is not supported by this device")

    @abstractmethod
    def read_samples(self, num_samples: int) -> np.ndarray:
        """Read complex IQ samples.

        Args:
            num_samples: Number of complex samples to read.

        Returns:
            One-dimensional complex64 array of length exactly ``num_samples``.

        Raises:
            RuntimeError: When the device is not connected or the link drops.
        """
