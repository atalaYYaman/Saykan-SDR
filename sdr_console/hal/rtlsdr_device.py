"""RTL-SDR driver skeleton (full streaming not yet implemented)."""

from __future__ import annotations

import logging

import numpy as np

from sdr_console.hal.capabilities import DeviceCapabilities
from sdr_console.hal.errors import DeviceUnavailableError
from sdr_console.hal.interface import SDRDeviceInterface

logger = logging.getLogger(__name__)

RTLSDR_CAPABILITIES = DeviceCapabilities(
    min_freq_hz=24_000_000.0,
    max_freq_hz=1_766_000_000.0,
    supported_sample_rates_hz=(
        250_000.0,
        1_024_000.0,
        2_048_000.0,
        2_400_000.0,
        2_560_000.0,
        3_200_000.0,
    ),
    min_gain_db=0.0,
    max_gain_db=49.6,
    gain_modes=("manual", "automatic"),
)


class RtlSdrDevice(SDRDeviceInterface):
    """RTL-SDR placeholder implementing :class:`SDRDeviceInterface`.

    ``connect`` verifies that ``pyrtlsdr`` can be imported and then raises
    until the streaming path is implemented.
    """

    def __init__(
        self,
        sample_rate_hz: float = 2_048_000.0,
        center_freq_hz: float = 100_000_000.0,
        gain_db: float = 20.0,
        device_index: int = 0,
        capabilities: DeviceCapabilities = RTLSDR_CAPABILITIES,
    ) -> None:
        self._capabilities = capabilities
        self._center_freq_hz = float(center_freq_hz)
        self._sample_rate_hz = float(sample_rate_hz)
        self._gain_db = float(gain_db)
        self._gain_mode = "manual"
        self._device_index = int(device_index)
        self._connected = False

        self._capabilities.validate_freq_hz(self._center_freq_hz)
        self._capabilities.validate_sample_rate_hz(self._sample_rate_hz)
        self._capabilities.validate_gain_db(self._gain_db)

    @property
    def capabilities(self) -> DeviceCapabilities:
        return self._capabilities

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def center_freq_hz(self) -> float:
        return self._center_freq_hz

    @property
    def sample_rate_hz(self) -> float:
        return self._sample_rate_hz

    @property
    def gain_db(self) -> float:
        return self._gain_db

    @property
    def gain_mode(self) -> str:
        return self._gain_mode

    def connect(self) -> None:
        try:
            import rtlsdr  # noqa: F401  # type: ignore[import-untyped]
        except ImportError as exc:
            raise DeviceUnavailableError(
                "pyrtlsdr is not installed. Install pyrtlsdr and librtlsdr "
                "to enable RTL-SDR support."
            ) from exc
        raise DeviceUnavailableError(
            "RTL-SDR streaming is not implemented yet (skeleton driver)."
        )

    def disconnect(self) -> None:
        self._connected = False

    def set_center_freq(self, freq_hz: float) -> None:
        self._capabilities.validate_freq_hz(freq_hz)
        self._center_freq_hz = float(freq_hz)

    def set_sample_rate(self, rate_hz: float) -> None:
        self._capabilities.validate_sample_rate_hz(rate_hz)
        self._sample_rate_hz = float(rate_hz)

    def set_gain(self, gain_db: float) -> None:
        self._capabilities.validate_gain_db(gain_db)
        self._gain_db = float(gain_db)

    def set_gain_mode(self, mode: str) -> None:
        self._capabilities.validate_gain_mode(mode)
        self._gain_mode = mode

    def read_samples(self, num_samples: int) -> np.ndarray:
        raise RuntimeError("RtlSdrDevice is not connected")
