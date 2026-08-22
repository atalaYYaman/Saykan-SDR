"""Baraj karıştırma oturumu — politika + waveform + TX cihazı."""

from __future__ import annotations

import numpy as np

from sdr_console.ea.constants import MIN_JAM_ATTENUATION_DB
from sdr_console.ea.policy import JamParams, validate_jam_request
from sdr_console.ea.waveform import generate_barrage_noise
from sdr_console.tx.interface import TXCapableDevice


class JamSession:
    """Tek baraj yayını: onaylı start, süre dolunca cihaz timer'ı keser."""

    def __init__(self) -> None:
        self._active = False
        self._device: TXCapableDevice | None = None
        self._params: JamParams | None = None

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def params(self) -> JamParams | None:
        return self._params

    def start(
        self,
        device: TXCapableDevice,
        *,
        sample_rate_hz: float,
        freq_hz: float,
        bandwidth_hz: float,
        attenuation_db: float,
        duration_s: float,
        confirmed: bool,
        authorized_window: bool,
        rng: np.random.Generator | None = None,
    ) -> np.ndarray:
        """Politikayı doğrula, baraj IQ üret ve cyclic yayın başlat."""
        params = validate_jam_request(
            freq_hz=freq_hz,
            bandwidth_hz=bandwidth_hz,
            attenuation_db=attenuation_db,
            duration_s=duration_s,
            sample_rate_hz=sample_rate_hz,
            confirmed=confirmed,
            authorized_window=authorized_window,
        )
        iq = generate_barrage_noise(
            sample_rate_hz,
            params.bandwidth_hz,
            rng=rng,
        )
        device.set_min_attenuation_db(MIN_JAM_ATTENUATION_DB)
        device.set_tx_freq(params.freq_hz)
        device.set_tx_attenuation_db(params.attenuation_db)
        device.set_tx_bandwidth_hz(params.bandwidth_hz)
        device.transmit(iq, cyclic=True, max_duration_s=params.duration_s)
        self._device = device
        self._params = params
        self._active = True
        return iq

    def stop(self) -> None:
        """Yayını kes; cihazı serbest bırakmaz (UI ``disconnect`` eder)."""
        device = self._device
        self._device = None
        self._params = None
        self._active = False
        if device is None:
            return
        try:
            device.stop_tx()
        except Exception:
            pass
