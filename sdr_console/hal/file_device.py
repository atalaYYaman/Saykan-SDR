"""File-backed IQ playback device for deterministic testing."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from sdr_console.hal.capabilities import DeviceCapabilities
from sdr_console.hal.interface import SDRDeviceInterface
from sdr_console.hal.mock_device import MOCK_CAPABILITIES


class FileIQDevice(SDRDeviceInterface):
    """Loops a recorded complex IQ ``.npy`` file as if it were live samples."""

    def __init__(
        self,
        path: str | Path,
        sample_rate_hz: float = 2_048_000.0,
        center_freq_hz: float = 100_000_000.0,
        gain_db: float = 20.0,
        capabilities: DeviceCapabilities = MOCK_CAPABILITIES,
    ) -> None:
        self._path = Path(path)
        self._capabilities = capabilities
        self._sample_rate_hz = sample_rate_hz
        self._center_freq_hz = center_freq_hz
        self._gain_db = gain_db
        self._connected = False
        self._cursor = 0
        self._iq: np.ndarray = np.array([], dtype=np.complex64)

        self._capabilities.validate_freq_hz(center_freq_hz)
        self._capabilities.validate_sample_rate_hz(sample_rate_hz)
        self._capabilities.validate_gain_db(gain_db)

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
        loaded = np.load(self._path)
        if loaded.ndim != 1:
            raise ValueError(f"IQ fixture must be 1-D, got shape {loaded.shape}")
        self._iq = np.asarray(loaded, dtype=np.complex64)
        if self._iq.size == 0:
            raise ValueError(f"IQ fixture is empty: {self._path}")
        self._cursor = 0
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False
        self._iq = np.array([], dtype=np.complex64)
        self._cursor = 0

    def set_center_freq(self, freq_hz: float) -> None:
        self._capabilities.validate_freq_hz(freq_hz)
        self._center_freq_hz = freq_hz

    def set_sample_rate(self, rate_hz: float) -> None:
        self._capabilities.validate_sample_rate_hz(rate_hz)
        self._sample_rate_hz = rate_hz

    def set_gain(self, gain_db: float) -> None:
        self._capabilities.validate_gain_db(gain_db)
        self._gain_db = gain_db

    def read_samples(self, num_samples: int) -> np.ndarray:
        if not self._connected:
            raise RuntimeError("FileIQDevice is not connected")
        if num_samples <= 0:
            raise ValueError("num_samples must be positive")

        out = np.empty(num_samples, dtype=np.complex64)
        remaining = num_samples
        write_at = 0
        while remaining > 0:
            available = self._iq.size - self._cursor
            take = min(remaining, available)
            out[write_at : write_at + take] = self._iq[self._cursor : self._cursor + take]
            self._cursor += take
            write_at += take
            remaining -= take
            if self._cursor >= self._iq.size:
                self._cursor = 0
        return out
