"""Yakalama replay — onay zorunlu TX yayını."""

from __future__ import annotations

import numpy as np

from sdr_console.tx.capture_decoder import OokCapture
from sdr_console.tx.errors import ReplayNotConfirmedError
from sdr_console.tx.interface import TXCapableDevice
from sdr_console.tx.ook_encoder import encode_capture


def replay_capture(
    device: TXCapableDevice,
    capture: OokCapture,
    attenuation_db: float,
    max_duration_s: float | None,
    *,
    confirmed: bool = False,
    amplitude: float = 0.85,
    cyclic: bool = False,
) -> np.ndarray:
    """Yakalamayı yeniden üretip TX cihazında yayınla.

    ``confirmed`` açıkça ``True`` olmadan TX başlamaz. Dönen değer gönderilen
    IQ waveform'u (doğrulama/test için).
    """
    if not confirmed:
        raise ReplayNotConfirmedError(
            "TX replay requires explicit user confirmation. "
            "Set confirmed=True only after the operator approves transmission."
        )

    iq = encode_capture(capture, amplitude=amplitude)
    device.set_tx_attenuation_db(attenuation_db)
    device.transmit(iq, cyclic=cyclic, max_duration_s=max_duration_s)
    return iq
