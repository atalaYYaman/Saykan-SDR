"""UI controls for automatic band scanning."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from sdr_console.scan.controller import ScanMode, default_scan_step_hz, min_scan_step_hz


class ScanPanel(QGroupBox):
    """Frequency-range scan controls and progress display."""

    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()

    def __init__(
        self,
        *,
        sample_rate_hz: float,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Tarama Modu", parent)
        self.setMinimumWidth(0)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        default_step_hz = default_scan_step_hz(sample_rate_hz)
        min_step_hz = min_scan_step_hz(sample_rate_hz)

        self._start_freq_spin = QDoubleSpinBox()
        self._start_freq_spin.setSuffix(" MHz")
        self._start_freq_spin.setDecimals(3)
        self._start_freq_spin.setRange(0.001, 6_000.0)
        self._start_freq_spin.setValue(99.0)
        self._start_freq_spin.setSingleStep(0.1)

        self._end_freq_spin = QDoubleSpinBox()
        self._end_freq_spin.setSuffix(" MHz")
        self._end_freq_spin.setDecimals(3)
        self._end_freq_spin.setRange(0.001, 6_000.0)
        self._end_freq_spin.setValue(100.0)
        self._end_freq_spin.setSingleStep(0.1)

        self._step_spin = QDoubleSpinBox()
        self._step_spin.setSuffix(" kHz")
        self._step_spin.setDecimals(1)
        self._step_spin.setRange(min_step_hz / 1_000.0, 10_000.0)
        self._step_spin.setValue(default_step_hz / 1_000.0)
        self._step_spin.setSingleStep(max(min_step_hz / 1_000.0, 1.0))
        self._step_spin.setToolTip(
            "Tarama adımı. Minimum değer örnek hızının yarısıdır "
            f"({min_step_hz / 1_000.0:g} kHz)."
        )

        self._mode_combo = QComboBox()
        self._mode_combo.addItem("Tek tur", ScanMode.SINGLE)
        self._mode_combo.addItem("Sürekli (ileri-geri)", ScanMode.LOOP)
        self._mode_combo.setToolTip(
            "Tek tur: aralığı bir kez tarar ve durur. "
            "Sürekli: başlangıçtan bitişe, sonra bitişten başlangıca döner; "
            "manuel durdurulana kadar devam eder."
        )

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(6)
        form.addRow("Başlangıç", self._start_freq_spin)
        form.addRow("Bitiş", self._end_freq_spin)
        form.addRow("Adım", self._step_spin)
        form.addRow("Mod", self._mode_combo)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)

        self._status_label = QLabel("Hazır")
        self._status_label.setWordWrap(True)

        self._start_button = QPushButton("Taramayı Başlat")
        self._stop_button = QPushButton("Durdur")
        self._stop_button.setEnabled(False)
        for button in (self._start_button, self._stop_button):
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            button.setMinimumHeight(28)
        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        button_row.addWidget(self._start_button)
        button_row.addWidget(self._stop_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(8)
        layout.addLayout(form)
        layout.addWidget(self._progress)
        layout.addWidget(self._status_label)
        layout.addLayout(button_row)
        layout.addStretch()

        self._start_button.clicked.connect(self.start_requested.emit)
        self._stop_button.clicked.connect(self.stop_requested.emit)

    def set_sample_rate_hz(self, sample_rate_hz: float) -> None:
        """Update step minimum/default when the receiver sample rate changes."""
        min_step_hz = min_scan_step_hz(sample_rate_hz)
        default_step_hz = default_scan_step_hz(sample_rate_hz)
        min_khz = min_step_hz / 1_000.0
        current_khz = float(self._step_spin.value())

        self._step_spin.blockSignals(True)
        self._step_spin.setRange(min_khz, 10_000.0)
        self._step_spin.setSingleStep(max(min_khz, 1.0))
        if current_khz < min_khz:
            self._step_spin.setValue(min_khz)
        elif abs(current_khz - self._step_spin.value()) < 1e-9:
            self._step_spin.setValue(default_step_hz / 1_000.0)
        self._step_spin.blockSignals(False)

    def start_freq_hz(self) -> float:
        return float(self._start_freq_spin.value()) * 1_000_000.0

    def end_freq_hz(self) -> float:
        return float(self._end_freq_spin.value()) * 1_000_000.0

    def step_hz(self) -> float:
        return float(self._step_spin.value()) * 1_000.0

    def scan_mode(self) -> ScanMode:
        mode = self._mode_combo.currentData()
        if isinstance(mode, ScanMode):
            return mode
        return ScanMode.SINGLE

    def validate_step_hz(self, sample_rate_hz: float) -> str | None:
        """Return a user-facing warning when the step is below the minimum."""
        minimum_hz = min_scan_step_hz(sample_rate_hz)
        if self.step_hz() + 1e-6 < minimum_hz:
            return (
                f"Adım boyutu en az {minimum_hz / 1_000.0:g} kHz olmalıdır "
                f"(örnek hızının yarısı)."
            )
        return None

    def set_status_message(self, message: str) -> None:
        self._status_label.setText(message)

    def set_scanning(self, scanning: bool) -> None:
        self._start_button.setEnabled(not scanning)
        self._stop_button.setEnabled(scanning)
        self._start_freq_spin.setEnabled(not scanning)
        self._end_freq_spin.setEnabled(not scanning)
        self._step_spin.setEnabled(not scanning)
        self._mode_combo.setEnabled(not scanning)
        if not scanning:
            self._status_label.setText("Hazır")

    def update_progress(
        self,
        step_index: int,
        step_count: int,
        center_freq_hz: float,
        *,
        round_index: int = 1,
        forward: bool = True,
    ) -> None:
        if step_count <= 0:
            self._progress.setValue(0)
            self._status_label.setText("Hazır")
            return

        completed = min(step_index + 1, step_count)
        percent = int(round(100.0 * completed / step_count))
        self._progress.setValue(percent)
        direction = "ileri" if forward else "geri"
        self._status_label.setText(
            f"Tur {round_index} {direction} — "
            f"{completed}/{step_count} — {center_freq_hz / 1_000_000.0:.3f} MHz"
        )

    def reset_progress(self) -> None:
        self._progress.setValue(0)
