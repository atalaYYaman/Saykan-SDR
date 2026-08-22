"""ADALM-Pluto TX sürücüsü (pyadi-iio, lazy import).

Aynı USB oturumunda RX ile birlikte çalışmak için mevcut ``adi.Pluto``
handle'ı paylaşılabilir; ikinci bir IIO context açılmaz.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

import numpy as np

from sdr_console.hal.errors import DeviceConnectionError, DeviceUnavailableError
from sdr_console.tx.constants import (
    DEFAULT_TX_ATTENUATION_DB,
    DEFAULT_TX_BANDWIDTH_HZ,
    LOOPBACK_DIGITAL,
    LOOPBACK_OFF,
    MIN_TX_ATTENUATION_DB,
    TX_FULL_SCALE,
    TX_MUTE_ATTENUATION_DB,
)
from sdr_console.tx.interface import TXCapableDevice
from sdr_console.tx.mock_tx import (
    _resolve_max_duration,
    _validate_attenuation,
    _validate_min_attenuation_db,
)
from sdr_console.tx.waveform import analog_tx_rf_bandwidth_hz, clamp_bandwidth_hz

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
        bandwidth_hz: float = DEFAULT_TX_BANDWIDTH_HZ,
        shared_sdr: Any | None = None,
        shared_lock: threading.RLock | None = None,
        loopback_while_tx: bool = False,
        min_attenuation_db: float = MIN_TX_ATTENUATION_DB,
    ) -> None:
        if tx_buffer_size <= 0:
            raise ValueError("tx_buffer_size must be positive")
        if full_scale <= 0:
            raise ValueError("full_scale must be positive")
        if sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive")
        if bandwidth_hz <= 0:
            raise ValueError("bandwidth_hz must be positive")

        self._tx_freq_hz = float(tx_freq_hz)
        self._sample_rate_hz = float(sample_rate_hz)
        self._min_attenuation_db = _validate_min_attenuation_db(min_attenuation_db)
        self._attenuation_db = _validate_attenuation(
            attenuation_db,
            min_attenuation_db=self._min_attenuation_db,
        )
        self._uri = uri.strip()
        self._tx_buffer_size = int(tx_buffer_size)
        self._full_scale = float(full_scale)
        self._bandwidth_hz = float(bandwidth_hz)
        self._loopback_while_tx = bool(loopback_while_tx)

        self._owns_sdr = shared_sdr is None
        self._sdr: Any | None = shared_sdr
        self._connected = False
        self._is_transmitting = False
        self._lock = shared_lock if shared_lock is not None else threading.RLock()
        self._timer: threading.Timer | None = None

        if shared_sdr is not None:
            with self._lock:
                try:
                    self._sync_sample_rate_from_sdr()
                    self._apply_tx_settings()
                    self._connected = True
                except Exception:
                    self._sdr = None
                    raise

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def owns_sdr(self) -> bool:
        return self._owns_sdr

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

    @property
    def bandwidth_hz(self) -> float:
        return self._bandwidth_hz

    def connect(self) -> None:
        with self._lock:
            if self._connected:
                if self._sdr is not None:
                    self._apply_tx_settings()
                return
            if not self._owns_sdr:
                raise RuntimeError("Shared Pluto TX handle is missing")

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
                "Pluto TX connected uri=%r rate=%g freq=%g attenuation=%g dB shared=%s",
                self._uri or "auto",
                self._sample_rate_hz,
                self._tx_freq_hz,
                self._attenuation_db,
                not self._owns_sdr,
            )

    def disconnect(self) -> None:
        with self._lock:
            self.stop_tx()
            self._connected = False
            if self._owns_sdr:
                self._destroy_sdr()
            else:
                self._sdr = None

    def set_tx_freq(self, freq_hz: float) -> None:
        if freq_hz <= 0:
            raise ValueError("freq_hz must be positive")
        with self._lock:
            self._tx_freq_hz = float(freq_hz)
            if self._sdr is not None:
                self._sdr.tx_lo = int(self._tx_freq_hz)

    def set_min_attenuation_db(self, min_attenuation_db: float) -> None:
        with self._lock:
            self._min_attenuation_db = _validate_min_attenuation_db(min_attenuation_db)

    def set_tx_attenuation_db(self, attenuation_db: float) -> None:
        with self._lock:
            attenuation = _validate_attenuation(
                attenuation_db,
                min_attenuation_db=self._min_attenuation_db,
            )
            self._attenuation_db = attenuation
            if self._sdr is not None:
                self._sdr.tx_hardwaregain_chan0 = -self._attenuation_db

    def set_tx_bandwidth_hz(self, bandwidth_hz: float) -> None:
        if bandwidth_hz <= 0:
            raise ValueError("bandwidth_hz must be positive")
        with self._lock:
            self._bandwidth_hz = float(bandwidth_hz)
            if self._sdr is not None:
                self._sdr.tx_rf_bandwidth = int(
                    analog_tx_rf_bandwidth_hz(self._bandwidth_hz, self._sample_rate_hz)
                )

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
            self._destroy_tx_buffer(sdr)
            sdr.tx_cyclic_buffer = bool(cyclic)
            self._set_loopback(LOOPBACK_DIGITAL if self._loopback_while_tx else LOOPBACK_OFF)
            try:
                sdr.tx(scaled)
            except Exception as exc:
                self._set_loopback(LOOPBACK_OFF)
                raise RuntimeError(f"Pluto TX failed: {exc}") from exc

            self._is_transmitting = True
            self._timer = threading.Timer(duration_s, self._auto_stop)
            self._timer.daemon = True
            self._timer.start()

    def stop_tx(self) -> None:
        with self._lock:
            self._cancel_timer()
            if self._sdr is not None:
                self._set_loopback(LOOPBACK_OFF)
                self._destroy_tx_buffer(self._sdr)
                try:
                    self._sdr.tx_hardwaregain_chan0 = -TX_MUTE_ATTENUATION_DB
                except Exception:
                    logger.debug("TX mute failed", exc_info=True)
            self._is_transmitting = False

    def set_loopback_while_tx(self, enabled: bool) -> None:
        self._loopback_while_tx = bool(enabled)

    def _set_loopback(self, mode: int) -> None:
        if self._sdr is None or not hasattr(self._sdr, "loopback"):
            return
        try:
            self._sdr.loopback = int(mode)
        except Exception:
            logger.debug("Pluto loopback=%s failed", mode, exc_info=True)

    def _destroy_tx_buffer(self, sdr: Any) -> None:
        destroy = getattr(sdr, "tx_destroy_buffer", None)
        if callable(destroy):
            try:
                destroy()
            except Exception:
                logger.debug("tx_destroy_buffer failed", exc_info=True)

    def _auto_stop(self) -> None:
        self.stop_tx()

    def _cancel_timer(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _sync_sample_rate_from_sdr(self) -> None:
        if self._sdr is None:
            return
        try:
            rate = float(self._sdr.sample_rate)
        except Exception:
            return
        if rate > 0:
            self._sample_rate_hz = rate

    def _apply_tx_settings(self) -> None:
        assert self._sdr is not None
        sdr = self._sdr
        # RX akışı başladıktan sonra kanalları yeniden seçmek IIO tamponunu bozar.
        if getattr(sdr, "tx_enabled_channels", None) != [0]:
            sdr.tx_enabled_channels = [0]
        sdr.tx_buffer_size = self._tx_buffer_size
        if self._owns_sdr:
            sdr.sample_rate = int(self._sample_rate_hz)
        else:
            self._sync_sample_rate_from_sdr()
        occupied = clamp_bandwidth_hz(self._bandwidth_hz, self._sample_rate_hz)
        self._bandwidth_hz = occupied
        sdr.tx_rf_bandwidth = int(
            analog_tx_rf_bandwidth_hz(occupied, self._sample_rate_hz)
        )
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
