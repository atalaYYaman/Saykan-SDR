"""TX test-sinyali kontrol paneli — sinyal yayını; DSP yok."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from sdr_console.tx.constants import (
    DEFAULT_BURST_DURATION_S,
    DEFAULT_MAX_TX_DURATION_S,
    DEFAULT_TX_ATTENUATION_DB,
    DEFAULT_TX_BANDWIDTH_HZ,
    DEFAULT_TX_FREQ_HZ,
    DEFAULT_TX_INTERVAL_S,
    MIN_TX_ATTENUATION_DB,
)

DEFAULT_TX_FREQ_MHZ = DEFAULT_TX_FREQ_HZ / 1_000_000.0


class TxPanel(QGroupBox):
    """Gürültü+CW test yayını: tek sefer veya süreli döngü."""

    oneshot_requested = pyqtSignal()
    loop_requested = pyqtSignal()
    stop_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("TX / Test", parent)
        self.setMinimumWidth(0)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self._busy = False
        self._transmitting = False

        self._freq_spin = QDoubleSpinBox()
        self._freq_spin.setSuffix(" MHz")
        self._freq_spin.setDecimals(3)
        self._freq_spin.setRange(70.0, 6_000.0)
        self._freq_spin.setValue(DEFAULT_TX_FREQ_MHZ)
        self._freq_spin.setSingleStep(0.01)
        self._freq_spin.setToolTip(
            "TX merkez frekansı. Varsayılan 433.97 MHz (ISM). "
            "Yayın başlayınca alıcı bu frekansa hizalanır."
        )

        self._bandwidth_spin = QDoubleSpinBox()
        self._bandwidth_spin.setSuffix(" kHz")
        self._bandwidth_spin.setDecimals(1)
        self._bandwidth_spin.setRange(1.0, 20_000.0)
        self._bandwidth_spin.setValue(DEFAULT_TX_BANDWIDTH_HZ / 1_000.0)
        self._bandwidth_spin.setSingleStep(10.0)
        self._bandwidth_spin.setToolTip(
            "İşgal edilen bant genişliği. Gürültü bu bandın içine sıkıştırılır; "
            "ortada zayıf bir CW çizgisi durur. Örnekleme hızını aşamaz."
        )

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

        self._duration_spin = QDoubleSpinBox()
        self._duration_spin.setSuffix(" s")
        self._duration_spin.setDecimals(2)
        self._duration_spin.setRange(0.10, DEFAULT_MAX_TX_DURATION_S)
        self._duration_spin.setValue(DEFAULT_BURST_DURATION_S)
        self._duration_spin.setSingleStep(0.10)
        self._duration_spin.setToolTip(
            f"Her yayın parçasının süresi. Güvenlik tavanı {DEFAULT_MAX_TX_DURATION_S:.0f} s."
        )

        self._interval_spin = QDoubleSpinBox()
        self._interval_spin.setSuffix(" s")
        self._interval_spin.setDecimals(2)
        self._interval_spin.setRange(0.10, 60.0)
        self._interval_spin.setValue(DEFAULT_TX_INTERVAL_S)
        self._interval_spin.setSingleStep(0.10)
        self._interval_spin.setToolTip(
            "Sürekli kipte iki yayın arasındaki sessizlik. Tek seferde kullanılmaz."
        )

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(6)
        form.addRow("TX frekans", self._freq_spin)
        form.addRow("Bant genişliği", self._bandwidth_spin)
        form.addRow("Attenuation", self._attenuation_spin)
        form.addRow("Süre", self._duration_spin)
        form.addRow("Aralık", self._interval_spin)

        self._backend_label = QLabel("Simülasyon: Mock TX (gerçek RF yok)")
        self._backend_label.setWordWrap(True)

        self._safety_label = QLabel(
            "RF yayın yasal sorumluluğu kullanıcıya aittir. "
            f"Varsayılan güç düşüktür (−{DEFAULT_TX_ATTENUATION_DB:.0f} dB). "
            f"Parça süresi en fazla {DEFAULT_MAX_TX_DURATION_S:.0f} s."
        )
        self._safety_label.setWordWrap(True)

        self._status_label = QLabel("Hazır")
        self._status_label.setWordWrap(True)

        self._oneshot_button = QPushButton("Tek sefer")
        self._loop_button = QPushButton("Sürekli")
        self._stop_button = QPushButton("TX Durdur")
        self._stop_button.setEnabled(False)
        for button in (self._oneshot_button, self._loop_button, self._stop_button):
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            button.setMinimumHeight(28)

        button_grid = QGridLayout()
        button_grid.setContentsMargins(0, 4, 0, 0)
        button_grid.setHorizontalSpacing(8)
        button_grid.setVerticalSpacing(8)
        button_grid.addWidget(self._oneshot_button, 0, 0)
        button_grid.addWidget(self._loop_button, 0, 1)
        button_grid.addWidget(self._stop_button, 1, 0, 1, 2)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(8)
        layout.addLayout(form)
        layout.addWidget(self._backend_label)
        layout.addWidget(self._safety_label)
        layout.addWidget(self._status_label)
        layout.addLayout(button_grid)
        layout.addStretch()

        self._oneshot_button.clicked.connect(self.oneshot_requested.emit)
        self._loop_button.clicked.connect(self.loop_requested.emit)
        self._stop_button.clicked.connect(self.stop_requested.emit)

    def tx_freq_hz(self) -> float:
        return float(self._freq_spin.value()) * 1_000_000.0

    def bandwidth_hz(self) -> float:
        return float(self._bandwidth_spin.value()) * 1_000.0

    def attenuation_db(self) -> float:
        return float(self._attenuation_spin.value())

    def duration_s(self) -> float:
        return float(self._duration_spin.value())

    def interval_s(self) -> float:
        return float(self._interval_spin.value())

    def set_backend_label(self, text: str) -> None:
        self._backend_label.setText(text)

    def set_status_message(self, message: str) -> None:
        self._status_label.setText(message)

    def set_busy(self, busy: bool) -> None:
        self._busy = bool(busy)
        self._update_buttons()

    def set_transmitting(self, transmitting: bool) -> None:
        self._transmitting = bool(transmitting)
        self._update_buttons()

    def is_busy(self) -> bool:
        return self._busy

    def is_transmitting(self) -> bool:
        return self._transmitting

    def _update_buttons(self) -> None:
        idle = not self._busy and not self._transmitting
        self._oneshot_button.setEnabled(idle)
        self._loop_button.setEnabled(idle)
        self._stop_button.setEnabled(self._transmitting)
        self._freq_spin.setEnabled(idle)
        self._bandwidth_spin.setEnabled(idle)
        self._attenuation_spin.setEnabled(idle)
        self._duration_spin.setEnabled(idle)
        self._interval_spin.setEnabled(idle)
