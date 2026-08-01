"""HackRF One driver skeleton (full streaming not yet implemented)."""

from __future__ import annotations

import logging

import numpy as np

from sdr_console.hal.capabilities import DeviceCapabilities
from sdr_console.hal.errors import DeviceUnavailableError
from sdr_console.hal.interface import SDRDeviceInterface

logger = logging.getLogger(__name__)

HACKRF_CAPABILITIES = DeviceCapabilities(
    min_freq_hz=1_000_000.0,
    max_freq_hz=6_000_000_000.0,
    supported_sample_rates_hz=(
        2_000_000.0,
        4_000_000.0,
        8_000_000.0,
        10_000_000.0,
        12_500_000.0,
        16_000_000.0,
        20_000_000.0,
    ),
    min_gain_db=0.0,
    max_gain_db=62.0,  # LNA 0-40 + VGA 0-62 typical combined UI range
    min_sample_rate_hz=2_000_000.0,
    max_sample_rate_hz=20_000_000.0,
    gain_modes=("manual",),
)


class HackRfDevice(SDRDeviceInterface):
    """HackRF One placeholder implementing :class:`SDRDeviceInterface`.

    ``connect`` verifies that a HackRF Python binding can be imported and
    then raises until the streaming path is implemented.
    """

    def __init__(
        self,
        sample_rate_hz: float = 10_000_000.0,
        center_freq_hz: float = 100_000_000.0,
        gain_db: float = 30.0,
        capabilities: DeviceCapabilities = HACKRF_CAPABILITIES,
    ) -> None:
        self._capabilities = capabilities
        self._center_freq_hz = float(center_freq_hz)
        self._sample_rate_hz = float(sample_rate_hz)
        self._gain_db = float(gain_db)
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

    def connect(self) -> None:
        binding = _try_import_hackrf()
        if binding is None:
            raise DeviceUnavailableError(
                "HackRF Python bindings are not installed. Install "
                "python-hackrf (and HackRF host software / DLLs) to enable "
                "HackRF support."
            )
        raise DeviceUnavailableError(
            "HackRF streaming is not implemented yet (skeleton driver)."
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

    def read_samples(self, num_samples: int) -> np.ndarray:
        raise RuntimeError("HackRfDevice is not connected")


def _try_import_hackrf() -> object | None:
    """Return an imported HackRF module, or None when unavailable."""
    for name in ("python_hackrf", "pyhackrf2", "hackrf"):
        try:
            return __import__(name)
        except ImportError:
            continue
    return None
