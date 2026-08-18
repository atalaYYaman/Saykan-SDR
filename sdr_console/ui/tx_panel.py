"""TX / Replay kontrol paneli — sinyal yayını; DSP yok."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from sdr_console.tx.constants import (
    DEFAULT_MAX_TX_DURATION_S,
    DEFAULT_TX_ATTENUATION_DB,
    MIN_TX_ATTENUATION_DB,
)

DEFAULT_TX_FREQ_MHZ = 433.92
DEFAULT_CAPTURE_DURATION_S = 0.3
DEFAULT_TX_DURATION_S = 1.0


class TxPanel(QGroupBox):
    """Yakalama, kayan kod durumu ve onaylı replay kontrolleri."""

    capture_requested = pyqtSignal()
    replay_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    clear_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("TX / Replay", parent)
        self.setMinimumWidth(280)
        self.setMaximumWidth(420)
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Preferred,
        )

        self._has_capture = False
        self._busy = False
        self._transmitting = False

        self._freq_spin = QDoubleSpinBox()
        self._freq_spin.setSuffix(" MHz")
        self._freq_spin.setDecimals(3)
        self._freq_spin.setRange(70.0, 6_000.0)
        self._freq_spin.setValue(DEFAULT_TX_FREQ_MHZ)
        self._freq_spin.setSingleStep(0.01)
        self._freq_spin.setToolTip("TX merkez frekansı. Varsayılan 433.92 MHz (ISM).")

        self._attenuation_spin = QDoubleSpinBox()
        self._attenuation_spin.setSuffix(" dB")
        self._attenuation_spin.setDecimals(1)
        self._attenuation_spin.setRange(MIN_TX_ATTENUATION_DB, 89.0)
        self._attenuation_spin.setValue(DEFAULT_TX_ATTENUATION_DB)
        self._attenuation_spin.setSingleStep(1.0)
        self._attenuation_spin.setToolTip(
            f"Yüksek değer = daha zayıf yayın. Minimum güvenlik sınırı "
            f"{MIN_TX_ATTENUATION_DB:.0f} dB (tx_hardwaregain ≤ -{MIN_TX_ATTENUATION_DB:.0f} dB)."
        )

        self._max_duration_spin = QDoubleSpinBox()
        self._max_duration_spin.setSuffix(" s")
        self._max_duration_spin.setDecimals(2)
        self._max_duration_spin.setRange(0.10, DEFAULT_MAX_TX_DURATION_S)
        self._max_duration_spin.setValue(DEFAULT_TX_DURATION_S)
        self._max_duration_spin.setSingleStep(0.10)
        self._max_duration_spin.setToolTip(
            "Yayın bu süre sonunda otomatik durur; sonsuz TX yok."
        )

        self._capture_duration_spin = QDoubleSpinBox()
        self._capture_duration_spin.setSuffix(" s")
        self._capture_duration_spin.setDecimals(2)
        self._capture_duration_spin.setRange(0.05, 2.0)
        self._capture_duration_spin.setValue(DEFAULT_CAPTURE_DURATION_S)
        self._capture_duration_spin.setSingleStep(0.05)
        self._capture_duration_spin.setToolTip(
            "RX akışından alınacak yakalama süresi. Önce Start ile dinlemeyi açın."
        )

        form = QFormLayout()
        form.addRow("TX frekans", self._freq_spin)
        form.addRow("Attenuation", self._attenuation_spin)
        form.addRow("Max süre", self._max_duration_spin)
        form.addRow("Yakalama", self._capture_duration_spin)

        self._backend_label = QLabel("Simülasyon: Mock TX (gerçek RF yok)")
        self._backend_label.setWordWrap(True)

        self._safety_label = QLabel(
            "RF yayın yasal sorumluluğu kullanıcıya aittir. "
            f"Varsayılan güç düşüktür (−{DEFAULT_TX_ATTENUATION_DB:.0f} dB)."
        )
        self._safety_label.setWordWrap(True)

        self._capture_label = QLabel("Yakalama yok")
        self._capture_label.setWordWrap(True)

        self._rolling_label = QLabel("Kayan kod: henüz yeterli yakalama yok.")
        self._rolling_label.setWordWrap(True)

        self._status_label = QLabel("Hazır")
        self._status_label.setWordWrap(True)

        self._capture_button = QPushButton("Yakala")
        self._replay_button = QPushButton("Replay")
        self._stop_button = QPushButton("TX Durdur")
        self._clear_button = QPushButton("Yakalamaları temizle")
        self._replay_button.setEnabled(False)
        self._stop_button.setEnabled(False)

        button_row = QHBoxLayout()
        button_row.addWidget(self._capture_button)
        button_row.addWidget(self._replay_button)
        button_row.addWidget(self._stop_button)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._backend_label)
        layout.addWidget(self._safety_label)
        layout.addWidget(self._capture_label)
        layout.addWidget(self._rolling_label)
        layout.addWidget(self._status_label)
        layout.addLayout(button_row)
        layout.addWidget(self._clear_button)

        self._capture_button.clicked.connect(self.capture_requested.emit)
        self._replay_button.clicked.connect(self.replay_requested.emit)
        self._stop_button.clicked.connect(self.stop_requested.emit)
        self._clear_button.clicked.connect(self.clear_requested.emit)

    def tx_freq_hz(self) -> float:
        return float(self._freq_spin.value()) * 1_000_000.0

    def attenuation_db(self) -> float:
        return float(self._attenuation_spin.value())

    def max_duration_s(self) -> float:
        return float(self._max_duration_spin.value())

    def capture_duration_s(self) -> float:
        return float(self._capture_duration_spin.value())

    def set_backend_label(self, text: str) -> None:
        self._backend_label.setText(text)

    def set_status_message(self, message: str) -> None:
        self._status_label.setText(message)

    def set_capture_summary(self, text: str) -> None:
        self._capture_label.setText(text)

    def set_rolling_code_status(self, message: str, *, warning: bool = False) -> None:
        self._rolling_label.setText(message)
        if warning:
            self._rolling_label.setStyleSheet("color: #c9a227;")
        else:
            self._rolling_label.setStyleSheet("")

    def set_has_capture(self, has_capture: bool) -> None:
        self._has_capture = bool(has_capture)
        self._update_buttons()

    def set_busy(self, busy: bool) -> None:
        self._busy = bool(busy)
        self._update_buttons()

    def set_transmitting(self, transmitting: bool) -> None:
        self._transmitting = bool(transmitting)
        self._update_buttons()

    def has_capture(self) -> bool:
        return self._has_capture

    def is_busy(self) -> bool:
        return self._busy

    def is_transmitting(self) -> bool:
        return self._transmitting

    def _update_buttons(self) -> None:
        idle = not self._busy and not self._transmitting
        self._capture_button.setEnabled(idle)
        self._replay_button.setEnabled(idle and self._has_capture)
        self._clear_button.setEnabled(idle)
        self._stop_button.setEnabled(self._transmitting)
        self._freq_spin.setEnabled(idle)
        self._attenuation_spin.setEnabled(idle)
        self._max_duration_spin.setEnabled(idle)
        self._capture_duration_spin.setEnabled(idle)
