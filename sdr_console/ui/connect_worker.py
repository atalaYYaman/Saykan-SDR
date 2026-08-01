"""Background QThread that opens an SDR device without blocking the GUI."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from sdr_console.hal.interface import SDRDeviceInterface


class ConnectWorker(QThread):
    """Call ``device.connect()`` on a worker thread.

    Emits ``connected`` on success or ``failed(message)`` on any exception.
    """

    connected = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, device: SDRDeviceInterface, parent=None) -> None:
        super().__init__(parent)
        self._device = device

    def run(self) -> None:
        try:
            self._device.connect()
        except Exception as exc:
            self.failed.emit(str(exc) or exc.__class__.__name__)
            return
        self.connected.emit()
