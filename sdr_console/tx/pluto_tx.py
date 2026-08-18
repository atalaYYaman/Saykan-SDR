"""ADALM-Pluto TX sürücüsü (pyadi-iio, lazy import)."""

from __future__ import annotations

import logging
import threading
from typing import Any

import numpy as np

from sdr_console.hal.errors import DeviceConnectionError, DeviceUnavailableError
from sdr_console.tx.constants import (
    DEFAULT_MAX_TX_DURATION_S,
    DEFAULT_TX_ATTENUATION_DB,
    MIN_TX_ATTENUATION_DB,
    TX_FULL_SCALE,
)
from sdr_console.tx.errors import TXAttenuationLimitError
from sdr_console.tx.interface import TXCapableDevice
from sdr_console.tx.mock_tx import _resolve_max_duration, _validate_attenuation

logger = logging.getLogger(__name__)


class PlutoTXDevice(TXCapableDevice):
    """ADALM-Pluto TX kanalı; ``adi.Pluto`` üzerinden yayın yapar."""

    def __init__(
        self,
        tx_freq_hz: float = 433_920_000.0,
        sample_rate_hz: float = 2_048_000.0,
        attenuation_db: float = DEFAULT_TX_ATTENUATION_DB,
        uri: str = "",
        tx_buffer_size: int = 16_384,
        full_scale: float = TX_FULL_SCALE,
    ) -> None:
        if tx_buffer_size <= 0:
            raise ValueError("tx_buffer_size must be positive")
        if full_scale <= 0:
            raise ValueError("full_scale must be positive")
        if sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive")

        self._tx_freq_hz = float(tx_freq_hz)
        self._sample_rate_hz = float(sample_rate_hz)
        self._attenuation_db = _validate_attenuation(attenuation_db)
        self._uri = uri.strip()
        self._tx_buffer_size = int(tx_buffer_size)
        self._full_scale = float(full_scale)

        self._sdr: Any | None = None
        self._connected = False
        self._is_transmitting = False
        self._lock = threading.RLock()
        self._timer: threading.Timer | None = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_transmitting(self) -> bool:
        with self._lock:
            return self._is_transmitting

    @property
    def tx_freq_hz(self) -> float:
        return self._tx_freq_hz

    @property
    def sample_rate_hz(self) -> float:
        return self._sample_rate_hz

    @property
    def attenuation_db(self) -> float:
        return self._attenuation_db

    def connect(self) -> None:
        with self._lock:
            if self._connected:
                return

            try:
                import adi  # type: ignore[import-untyped]
            except ImportError as exc:
                raise DeviceUnavailableError(
                    "pyadi-iio is not installed. Install with: pip install -e \".[pluto]\""
                ) from exc

            try:
                if self._uri:
                    sdr = adi.Pluto(uri=self._uri)
                else:
                    sdr = adi.Pluto()
            except Exception as exc:
                raise DeviceConnectionError(
                    "Failed to open ADALM-Pluto for TX"
                    + (f" at {self._uri!r}" if self._uri else "")
                    + f": {exc}"
                ) from exc

            self._sdr = sdr
            try:
                self._apply_tx_settings()
            except Exception:
                self._destroy_sdr()
                raise

            self._connected = True
            logger.info(
                "Pluto TX connected uri=%r rate=%g freq=%g attenuation=%g dB",
                self._uri or "auto",
                self._sample_rate_hz,
                self._tx_freq_hz,
                self._attenuation_db,
            )

    def disconnect(self) -> None:
        with self._lock:
            self.stop_tx()
            self._connected = False
            self._destroy_sdr()

    def set_tx_freq(self, freq_hz: float) -> None:
        if freq_hz <= 0:
            raise ValueError("freq_hz must be positive")
        with self._lock:
            self._tx_freq_hz = float(freq_hz)
            if self._sdr is not None:
                self._sdr.tx_lo = int(self._tx_freq_hz)

    def set_tx_attenuation_db(self, attenuation_db: float) -> None:
        attenuation = _validate_attenuation(attenuation_db)
        with self._lock:
            self._attenuation_db = attenuation
            if self._sdr is not None:
                self._sdr.tx_hardwaregain_chan0 = -self._attenuation_db

    def transmit(
        self,
        iq: np.ndarray,
        cyclic: bool,
        max_duration_s: float | None,
    ) -> None:
        if not self._connected or self._sdr is None:
            raise RuntimeError("PlutoTXDevice is not connected")

        arr = np.asarray(iq)
        if arr.ndim != 1:
            arr = arr.reshape(-1)
        if arr.size == 0:
            raise ValueError("iq must contain at least one sample")

        duration_s = _resolve_max_duration(max_duration_s)
        scaled = (arr.astype(np.complex128) * self._full_scale).astype(np.complex64)

        with self._lock:
            if not self._connected or self._sdr is None:
                raise RuntimeError("PlutoTXDevice is not connected")

            self._cancel_timer()
            sdr = self._sdr
            sdr.tx_cyclic_buffer = bool(cyclic)
            try:
                sdr.tx(scaled)
            except Exception as exc:
                raise RuntimeError(f"Pluto TX failed: {exc}") from exc

            self._is_transmitting = True
            self._timer = threading.Timer(duration_s, self._auto_stop)
            self._timer.daemon = True
            self._timer.start()

    def stop_tx(self) -> None:
        with self._lock:
            self._cancel_timer()
            if self._sdr is not None:
                destroy = getattr(self._sdr, "tx_destroy_buffer", None)
                if callable(destroy):
                    try:
                        destroy()
                    except Exception:
                        logger.debug("tx_destroy_buffer failed", exc_info=True)
            self._is_transmitting = False

    def _auto_stop(self) -> None:
        self.stop_tx()

    def _cancel_timer(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _apply_tx_settings(self) -> None:
        assert self._sdr is not None
        sdr = self._sdr
        sdr.tx_enabled_channels = [0]
        sdr.tx_buffer_size = self._tx_buffer_size
        sdr.sample_rate = int(self._sample_rate_hz)
        sdr.tx_rf_bandwidth = int(self._sample_rate_hz)
        sdr.tx_lo = int(self._tx_freq_hz)
        sdr.tx_hardwaregain_chan0 = -self._attenuation_db

    def _destroy_sdr(self) -> None:
        sdr = self._sdr
        self._sdr = None
        if sdr is None:
            return
        try:
            destroy = getattr(sdr, "tx_destroy_buffer", None)
            if callable(destroy):
                destroy()
        except Exception:
            logger.debug("tx_destroy_buffer failed during disconnect", exc_info=True)
        try:
            del sdr
        except Exception:
            pass
