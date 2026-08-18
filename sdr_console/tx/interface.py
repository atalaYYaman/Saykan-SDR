"""TX donanım arayüzü."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class TXCapableDevice(ABC):
    """433 MHz ISM replay gibi TX işlemleri için ortak sözleşme."""

    @abstractmethod
    def set_tx_freq(self, freq_hz: float) -> None:
        """TX merkez frekansını Hz cinsinden ayarla."""

    @abstractmethod
    def set_tx_attenuation_db(self, attenuation_db: float) -> None:
        """TX attenuation'ı dB cinsinden ayarla (yüksek = daha zayıf yayın)."""

    @abstractmethod
    def transmit(
        self,
        iq: np.ndarray,
        cyclic: bool,
        max_duration_s: float | None,
    ) -> None:
        """IQ waveform'u yayınla.

        ``max_duration_s`` None ise makul bir varsayılan süreye düşer; süre
        dolduğunda otomatik ``stop_tx()`` çağrılır.
        """

    @abstractmethod
    def stop_tx(self) -> None:
        """Yayını durdur ve TX buffer'ını serbest bırak."""
