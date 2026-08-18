"""Thread-safe snapshot of confirmed signal detections for UI polling."""

from __future__ import annotations

import threading

from sdr_console.detect.identified import IdentifiedPeak


class DetectionState:
    """Latest confirmed peaks shared between the detection worker and the UI."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._peaks: tuple[IdentifiedPeak, ...] = ()

    def replace(self, peaks: list[IdentifiedPeak]) -> None:
        with self._lock:
            self._peaks = tuple(peaks)

    def clear(self) -> None:
        with self._lock:
            self._peaks = ()

    def snapshot(self) -> list[IdentifiedPeak]:
        with self._lock:
            return list(self._peaks)
