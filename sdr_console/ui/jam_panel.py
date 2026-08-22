"""Baraj karıştırma paneli — onaylı kısa yayın; DSP yok."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from sdr_console.ea.constants import (
    DEFAULT_JAM_ATTENUATION_DB,
    DEFAULT_JAM_BANDWIDTH_HZ,
    DEFAULT_JAM_DURATION_S,
    DEFAULT_JAM_FREQ_HZ,
    MAX_JAM_DURATION_S,
    MIN_JAM_ATTENUATION_DB,
    MIN_JAM_BANDWIDTH_HZ,
    MIN_JAM_DURATION_S,
)

DEFAULT_JAM_FREQ_MHZ = DEFAULT_JAM_FREQ_HZ / 1_000_000.0
_JAM_TYPE_BARRAGE_INDEX = 2


class JamPanel(QGroupBox):
    """Baraj demosu: bant gürültüsü, onay + yetkili pencere."""

    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    copy_detection_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Karıştırma", parent)
        self.setMinimumWidth(0)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self._busy = False
        self._transmitting = False

        self._note = QLabel("Baraj demosu — onaylı kısa yayın")
        self._note.setObjectName("jam_demo_note")
        self._note.setWordWrap(True)

        self._type_combo = QComboBox()
        self._type_combo.setObjectName("jam_type")
        self._type_combo.addItems(["Tekli", "Çoklu", "Baraj"])
        self._type_combo.setCurrentIndex(_JAM_TYPE_BARRAGE_INDEX)
        self._type_combo.setEnabled(False)
        self._type_combo.setToolTip(
            "Bu tur yalnız baraj. Tekli / çoklu ve look-through SHELL."
        )

        self._freq_spin = QDoubleSpinBox()
        self._freq_spin.setObjectName("jam_freq")
        self._freq_spin.setSuffix(" MHz")
        self._freq_spin.setDecimals(3)
        self._freq_spin.setRange(70.0, 6_000.0)
        self._freq_spin.setValue(DEFAULT_JAM_FREQ_MHZ)
        self._freq_spin.setSingleStep(0.01)
        self._freq_spin.setToolTip("Baraj merkez frekansı.")

        self._copy_button = QPushButton("Tespitten kopyala")
        self._copy_button.setObjectName("jam_copy_detection")
        self._copy_button.setToolTip("Seçili tespit satırının frekansını al.")

        freq_row = QWidget()
        freq_layout = QHBoxLayout(freq_row)
        freq_layout.setContentsMargins(0, 0, 0, 0)
        freq_layout.setSpacing(8)
        freq_layout.addWidget(self._freq_spin, stretch=1)
        freq_layout.addWidget(self._copy_button)

        self._bandwidth_spin = QDoubleSpinBox()
        self._bandwidth_spin.setObjectName("jam_bandwidth")
        self._bandwidth_spin.setSuffix(" kHz")
        self._bandwidth_spin.setDecimals(1)
        self._bandwidth_spin.setRange(
            MIN_JAM_BANDWIDTH_HZ / 1_000.0,
            20_000.0,
        )
        self._bandwidth_spin.setValue(DEFAULT_JAM_BANDWIDTH_HZ / 1_000.0)
        self._bandwidth_spin.setSingleStep(100.0)
        self._bandwidth_spin.setToolTip(
            "İşgal edilen baraj genişliği. Örnekleme hızını aşamaz "
            "(eşzamanlı RX+TX ≤ sample rate)."
        )

        self._attenuation_spin = QDoubleSpinBox()
        self._attenuation_spin.setObjectName("jam_attenuation")
        self._attenuation_spin.setSuffix(" dB")
        self._attenuation_spin.setDecimals(1)
        self._attenuation_spin.setRange(MIN_JAM_ATTENUATION_DB, 89.0)
        self._attenuation_spin.setValue(DEFAULT_JAM_ATTENUATION_DB)
        self._attenuation_spin.setSingleStep(1.0)
        self._attenuation_spin.setToolTip(
            f"Yüksek değer = daha zayıf yayın. Karıştırma tabanı "
            f"{MIN_JAM_ATTENUATION_DB:.0f} dB (TX/Test 40 dB ayrı kalır)."
        )

        self._duration_spin = QDoubleSpinBox()
        self._duration_spin.setObjectName("jam_duration")
        self._duration_spin.setSuffix(" s")
        self._duration_spin.setDecimals(2)
        self._duration_spin.setRange(MIN_JAM_DURATION_S, MAX_JAM_DURATION_S)
        self._duration_spin.setValue(DEFAULT_JAM_DURATION_S)
        self._duration_spin.setSingleStep(0.10)
        self._duration_spin.setToolTip(
            f"Yayın süresi. Güvenlik tavanı {MAX_JAM_DURATION_S:.0f} s; sonsuz TX yok."
        )

        self._loopback_check = QCheckBox("Çip içi loopback (RF değil)")
        self._loopback_check.setObjectName("jam_loopback")
        self._loopback_check.setChecked(False)
        self._loopback_check.setToolTip(
            "Açıkken AD9363 TX IQ'sunu antene gitmeden RX yoluna kopyalar. "
            "Gerçek RF barajı için kapalı tutun."
        )

        self._lookthrough = QCheckBox("Komite penceresi / look-through")
        self._lookthrough.setObjectName("jam_lookthrough")
        self._lookthrough.setEnabled(False)
        self._lookthrough.setToolTip("Arabakışlı kip bu turda SHELL — bağlı değil.")

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(6)
        form.addRow("Tip", self._type_combo)
        form.addRow("TX frekans", freq_row)
        form.addRow("Baraj BW", self._bandwidth_spin)
        form.addRow("Attenuation", self._attenuation_spin)
        form.addRow("Süre", self._duration_spin)
        form.addRow("", self._loopback_check)

        self._backend_label = QLabel("Simülasyon: Mock TX (gerçek RF yok)")
        self._backend_label.setWordWrap(True)

        self._safety_label = QLabel(
            "Kapalı test barajı: bant gürültüsü, onay + yetkili pencere. "
            f"Attenuation en az {MIN_JAM_ATTENUATION_DB:.0f} dB, süre en fazla "
            f"{MAX_JAM_DURATION_S:.0f} s. TX/Test 40 dB / 5 s tavanı değişmez. "
            "İşgal ≤ sample rate (±Fs/2)."
        )
        self._safety_label.setWordWrap(True)

        self._status_label = QLabel("Hazır")
        self._status_label.setObjectName("jam_status")
        self._status_label.setWordWrap(True)

        self._start_button = QPushButton("Start")
        self._start_button.setObjectName("jam_start")
        self._stop_button = QPushButton("Stop")
        self._stop_button.setObjectName("jam_stop")
        self._stop_button.setEnabled(False)
        for button in (self._start_button, self._stop_button):
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            button.setMinimumHeight(28)

        button_grid = QGridLayout()
        button_grid.setContentsMargins(0, 4, 0, 0)
        button_grid.setHorizontalSpacing(8)
        button_grid.addWidget(self._start_button, 0, 0)
        button_grid.addWidget(self._stop_button, 0, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(8)
        layout.addWidget(self._note)
        layout.addLayout(form)
        layout.addWidget(self._lookthrough)
        layout.addWidget(self._backend_label)
        layout.addWidget(self._safety_label)
        layout.addWidget(self._status_label)
        layout.addLayout(button_grid)
        layout.addStretch()

        self._start_button.clicked.connect(self.start_requested.emit)
        self._stop_button.clicked.connect(self.stop_requested.emit)
        self._copy_button.clicked.connect(self.copy_detection_requested.emit)

    def note_text(self) -> str:
        return self._note.text()

    def jam_type_text(self) -> str:
        return self._type_combo.currentText()

    def tx_freq_hz(self) -> float:
        return float(self._freq_spin.value()) * 1_000_000.0

    def set_freq_hz(self, freq_hz: float) -> None:
        mhz = float(freq_hz) / 1_000_000.0
        self._freq_spin.setValue(mhz)

    def bandwidth_hz(self) -> float:
        return float(self._bandwidth_spin.value()) * 1_000.0

    def set_max_bandwidth_hz(self, sample_rate_hz: float) -> None:
        """Baraj BW tavanını mevcut örnekleme hızına çek."""
        rate_khz = max(MIN_JAM_BANDWIDTH_HZ / 1_000.0, float(sample_rate_hz) / 1_000.0)
        self._bandwidth_spin.setMaximum(rate_khz)
        if self._bandwidth_spin.value() > rate_khz:
            self._bandwidth_spin.setValue(rate_khz)

    def attenuation_db(self) -> float:
        return float(self._attenuation_spin.value())

    def duration_s(self) -> float:
        return float(self._duration_spin.value())

    def loopback_enabled(self) -> bool:
        return self._loopback_check.isChecked()

    def lookthrough_enabled(self) -> bool:
        return False

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
        self._start_button.setEnabled(idle)
        self._stop_button.setEnabled(self._transmitting)
        self._freq_spin.setEnabled(idle)
        self._bandwidth_spin.setEnabled(idle)
        self._attenuation_spin.setEnabled(idle)
        self._duration_spin.setEnabled(idle)
        self._loopback_check.setEnabled(idle)
        self._copy_button.setEnabled(idle)
        self._type_combo.setEnabled(False)
        self._lookthrough.setEnabled(False)
