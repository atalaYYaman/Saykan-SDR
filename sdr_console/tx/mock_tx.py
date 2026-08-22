"""Donanıma dokunmayan TX mock implementasyonu."""

from __future__ import annotations

import threading
from typing import Any

import numpy as np

from sdr_console.tx.constants import (
    ABSOLUTE_MIN_ATTENUATION_DB,
    DEFAULT_MAX_TX_DURATION_S,
    DEFAULT_TX_ATTENUATION_DB,
    DEFAULT_TX_BANDWIDTH_HZ,
    MIN_TX_ATTENUATION_DB,
)
from sdr_console.tx.errors import TXAttenuationLimitError
from sdr_console.tx.interface import TXCapableDevice


def _validate_min_attenuation_db(min_attenuation_db: float) -> float:
    floor = float(min_attenuation_db)
    if floor < ABSOLUTE_MIN_ATTENUATION_DB:
        raise TXAttenuationLimitError(
            f"TX attenuation tabanı {floor:.1f} dB mutlak sınırın altında; "
            f"minimum {ABSOLUTE_MIN_ATTENUATION_DB:.1f} dB gerekli."
        )
    return floor


def _validate_attenuation(
    attenuation_db: float,
    min_attenuation_db: float = MIN_TX_ATTENUATION_DB,
) -> float:
    floor = _validate_min_attenuation_db(min_attenuation_db)
    attenuation = float(attenuation_db)
    if attenuation < floor:
        raise TXAttenuationLimitError(
            f"TX attenuation {attenuation:.1f} dB güvenlik sınırının altında; "
            f"minimum {floor:.1f} dB gerekli "
            f"(tx_hardwaregain_chan0 <= {floor:.1f} dB zayıf)."
        )
    return attenuation


def _resolve_max_duration(max_duration_s: float | None) -> float:
    if max_duration_s is None:
        return DEFAULT_MAX_TX_DURATION_S
    duration = float(max_duration_s)
    if duration <= 0:
        raise ValueError("max_duration_s must be positive")
    return duration


class MockTXDevice(TXCapableDevice):
    """Yayın durumunu ve gönderilen IQ'yu kaydeden test TX cihazı."""

    def __init__(
        self,
        tx_freq_hz: float = 433_920_000.0,
        attenuation_db: float = DEFAULT_TX_ATTENUATION_DB,
        min_attenuation_db: float = MIN_TX_ATTENUATION_DB,
    ) -> None:
        self._tx_freq_hz = float(tx_freq_hz)
        self._min_attenuation_db = _validate_min_attenuation_db(min_attenuation_db)
        self._attenuation_db = _validate_attenuation(
            attenuation_db,
            min_attenuation_db=self._min_attenuation_db,
        )
        self._bandwidth_hz = float(DEFAULT_TX_BANDWIDTH_HZ)
        self._lock = threading.RLock()
        self._is_transmitting = False
        self._transmitted_iq: np.ndarray | None = None
        self._last_cyclic = False
        self._timer: threading.Timer | None = None
        self._history: list[dict[str, Any]] = []

    @property
    def tx_freq_hz(self) -> float:
        return self._tx_freq_hz

    @property
    def attenuation_db(self) -> float:
        return self._attenuation_db

    @property
    def is_transmitting(self) -> bool:
        with self._lock:
            return self._is_transmitting

    @property
    def transmitted_iq(self) -> np.ndarray | None:
        with self._lock:
            if self._transmitted_iq is None:
                return None
            return self._transmitted_iq.copy()

    @property
    def history(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._history)

    def set_tx_freq(self, freq_hz: float) -> None:
        if freq_hz <= 0:
            raise ValueError("freq_hz must be positive")
        with self._lock:
            self._tx_freq_hz = float(freq_hz)

    def set_min_attenuation_db(self, min_attenuation_db: float) -> None:
        with self._lock:
            self._min_attenuation_db = _validate_min_attenuation_db(min_attenuation_db)

    def set_tx_attenuation_db(self, attenuation_db: float) -> None:
        with self._lock:
            self._attenuation_db = _validate_attenuation(
                attenuation_db,
                min_attenuation_db=self._min_attenuation_db,
            )

    def set_tx_bandwidth_hz(self, bandwidth_hz: float) -> None:
        if bandwidth_hz <= 0:
            raise ValueError("bandwidth_hz must be positive")
        with self._lock:
            self._bandwidth_hz = float(bandwidth_hz)

    @property
    def bandwidth_hz(self) -> float:
        return self._bandwidth_hz

    def transmit(
        self,
        iq: np.ndarray,
        cyclic: bool,
        max_duration_s: float | None,
    ) -> None:
        arr = np.asarray(iq)
        if arr.ndim != 1:
            arr = arr.reshape(-1)
        if arr.size == 0:
            raise ValueError("iq must contain at least one sample")

        duration_s = _resolve_max_duration(max_duration_s)

        with self._lock:
            self._cancel_timer()
            self._transmitted_iq = arr.astype(np.complex64, copy=True)
            self._last_cyclic = bool(cyclic)
            self._is_transmitting = True
            self._history.append(
                {
                    "iq": self._transmitted_iq.copy(),
                    "cyclic": self._last_cyclic,
                    "max_duration_s": duration_s,
                    "freq_hz": self._tx_freq_hz,
                    "attenuation_db": self._attenuation_db,
                }
            )
            self._timer = threading.Timer(duration_s, self._auto_stop)
            self._timer.daemon = True
            self._timer.start()

    def stop_tx(self) -> None:
        with self._lock:
            self._cancel_timer()
            self._is_transmitting = False

    def _auto_stop(self) -> None:
        with self._lock:
            self._timer = None
            self._is_transmitting = False

    def _cancel_timer(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
