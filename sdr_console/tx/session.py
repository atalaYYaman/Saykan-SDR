"""TX replay oturumu — IQ biriktirme, yakalama listesi, kayan kod özeti."""

from __future__ import annotations

import numpy as np

from sdr_console.tx.capture_decoder import (
    OokCapture,
    RollingCodeAssessment,
    analyze_capture,
    assess_rolling_code,
)


def format_capture_summary(capture: OokCapture) -> str:
    """Kullanıcıya gösterilecek kısa yakalama özeti (numpy yok)."""
    pulse_count = len(capture.pulses)
    on_count = sum(1 for pulse in capture.pulses if pulse.level)
    if capture.bits is None:
        bits_text = "çözülemedi"
    else:
        bits_text = "".join(str(bit) for bit in capture.bits)
        if len(bits_text) > 48:
            bits_text = bits_text[:48] + "…"
    return f"{pulse_count} darbe ({on_count} ON), bitler: {bits_text}"


class ReplaySession:
    """Bir dizi OOK yakalamasını ve süren RX yakalama tamponunu tutar."""

    def __init__(self) -> None:
        self._captures: list[OokCapture] = []
        self._chunks: list[np.ndarray] = []
        self._collected = 0
        self._needed = 0
        self._capturing = False

    @property
    def captures(self) -> list[OokCapture]:
        return list(self._captures)

    @property
    def latest(self) -> OokCapture | None:
        return self._captures[-1] if self._captures else None

    @property
    def assessment(self) -> RollingCodeAssessment:
        return assess_rolling_code(self._captures)

    @property
    def is_capturing(self) -> bool:
        return self._capturing

    @property
    def collected_samples(self) -> int:
        return self._collected

    def begin_capture(self, needed_samples: int) -> None:
        """Yeni bir RX yakalama tamponu aç."""
        self._chunks = []
        self._collected = 0
        self._needed = max(1, int(needed_samples))
        self._capturing = True

    def ingest_block(self, iq: object) -> bool:
        """Bir IQ bloğu ekle; yeterli örnek toplandıysa ``True``.

        Acquisition worker aynı diziyi yeniden kullanabildiği için blok kopyalanır.
        """
        if not self._capturing:
            return False
        arr = np.asarray(iq)
        if arr.ndim != 1:
            arr = arr.reshape(-1)
        if arr.size == 0:
            return False
        self._chunks.append(np.array(arr, copy=True, dtype=np.complex64))
        self._collected += int(arr.size)
        return self._collected >= self._needed

    def abort_capture(self) -> None:
        """Süren yakalamayı iptal et; kayıtlı yakalamalara dokunma."""
        self._capturing = False
        self._chunks = []
        self._collected = 0
        self._needed = 0

    def finish_capture(self, sample_rate_hz: float) -> tuple[OokCapture, RollingCodeAssessment]:
        """Biriken IQ'yu çöz ve oturuma ekle."""
        if not self._chunks:
            self.abort_capture()
            raise ValueError("no IQ collected")
        iq = np.concatenate(self._chunks)
        self.abort_capture()
        capture = analyze_capture(iq, sample_rate_hz)
        self._captures.append(capture)
        return capture, assess_rolling_code(self._captures)

    def add_capture(self, capture: OokCapture) -> RollingCodeAssessment:
        """Hazır bir yakalamayı oturuma ekle (test / enjeksiyon)."""
        self._captures.append(capture)
        return assess_rolling_code(self._captures)

    def clear(self) -> None:
        self.abort_capture()
        self._captures.clear()
