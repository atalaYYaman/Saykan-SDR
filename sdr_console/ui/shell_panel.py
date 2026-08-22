"""SHELL feature panels — empty-state only, no fake telemetry (MASTER §5)."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


def _disabled(*widgets: QWidget) -> None:
    for widget in widgets:
        widget.setEnabled(False)


class ShellPanel(QGroupBox):
    """Placeholder dock body: one empty-state line plus disabled control slots."""

    def __init__(
        self,
        title: str,
        empty_text: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, parent)
        self.setProperty("shell", "true")
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._empty = QLabel(empty_text)
        self._empty.setObjectName("shell_empty_label")
        self._empty.setWordWrap(True)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._body = QVBoxLayout(self)
        self._body.setContentsMargins(8, 16, 8, 8)
        self._body.setSpacing(8)
        self._body.addWidget(self._empty)

    def body_layout(self) -> QVBoxLayout:
        return self._body

    def empty_text(self) -> str:
        return self._empty.text()

    def set_empty_text(self, text: str) -> None:
        self._empty.setText(text)


def create_df_shell() -> ShellPanel:
    panel = ShellPanel("Yön Bulma", "DF bağlı değil")
    method = QComboBox()
    method.addItems(["Genlik", "Faz", "TDOA"])
    bearing = QLineEdit()
    bearing.setPlaceholderText("bearing °")
    rms = QLineEdit()
    rms.setPlaceholderText("RMS °")
    form = QFormLayout()
    form.addRow("Yöntem", method)
    form.addRow("Bearing", bearing)
    form.addRow("RMS", rms)
    _disabled(method, bearing, rms)
    holder = QWidget()
    holder.setLayout(form)
    panel.body_layout().addWidget(holder)
    panel.body_layout().addStretch()
    return panel


def create_geoloc_shell() -> ShellPanel:
    panel = ShellPanel("Konum", "Konum kaynağı yok")
    map_slot = QLabel("Mini harita yuvası")
    map_slot.setAlignment(Qt.AlignmentFlag.AlignCenter)
    map_slot.setMinimumHeight(80)
    map_slot.setObjectName("shell_map_slot")
    note = QLineEdit()
    note.setPlaceholderText("Yer / hava notu")
    _disabled(map_slot, note)
    panel.body_layout().addWidget(map_slot)
    panel.body_layout().addWidget(note)
    panel.body_layout().addStretch()
    return panel


class ParamsShellPanel(ShellPanel):
    """Inspector for a selected detection: NOW VFO/BW, SHELL fields stay '—'."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Parametre", "Tespit seçin", parent)
        self._vfo = QLineEdit("—")
        self._vfo.setObjectName("params_vfo")
        self._vfo.setReadOnly(True)
        self._bw = QLineEdit("—")
        self._bw.setObjectName("params_bw")
        self._bw.setReadOnly(True)
        extra = QLineEdit("—")
        extra.setObjectName("params_shell_extra")
        extra.setReadOnly(True)
        extra.setEnabled(False)
        extra.setToolTip("Mod / protokol / EKKT — SHELL, bağlı değil")
        form = QFormLayout()
        form.addRow("VFO", self._vfo)
        form.addRow("BW", self._bw)
        form.addRow("Mod / protokol / EKKT", extra)
        holder = QWidget()
        holder.setLayout(form)
        self.body_layout().addWidget(holder)
        self.body_layout().addStretch()

    def set_selection(
        self,
        frequency_hz: float | None,
        bandwidth_hz: float = 0.0,
    ) -> None:
        if frequency_hz is None or frequency_hz <= 0.0:
            self.set_empty_text("Tespit seçin")
            self._vfo.setText("—")
            self._bw.setText("—")
            return
        self.set_empty_text("Seçili tespit")
        self._vfo.setText(f"{frequency_hz / 1_000_000.0:.6f} MHz")
        if bandwidth_hz > 0.0:
            self._bw.setText(f"{bandwidth_hz / 1_000.0:.1f} kHz")
        else:
            self._bw.setText("—")

    def vfo_text(self) -> str:
        return self._vfo.text()

    def bw_text(self) -> str:
        return self._bw.text()


def create_params_shell() -> ParamsShellPanel:
    return ParamsShellPanel()


def create_ea_deceive_shell() -> ShellPanel:
    panel = ShellPanel("Analog Aldatma", "Aldatma modülü bağlı değil")
    path = QLineEdit()
    path.setPlaceholderText("Ses / dalga şekli dosyası")
    _disabled(path)
    panel.body_layout().addWidget(path)
    panel.body_layout().addStretch()
    return panel


def create_ea_gnss_shell() -> ShellPanel:
    panel = ShellPanel("GNSS Aldatma", "GNSS aldatma bağlı değil")
    services = QWidget()
    grid = QVBoxLayout(services)
    grid.setContentsMargins(0, 0, 0, 0)
    boxes = [
        QCheckBox("GPS L1 (min)"),
        QCheckBox("GPS L2 / L5"),
        QCheckBox("GLONASS"),
        QCheckBox("Galileo"),
        QCheckBox("BeiDou"),
    ]
    for box in boxes:
        box.setChecked(False)
        _disabled(box)
        grid.addWidget(box)
    note = QLabel("Karıştırma ile birlikte, sonra veya bağımsız — backend yok.")
    note.setWordWrap(True)
    panel.body_layout().addWidget(services)
    panel.body_layout().addWidget(note)
    panel.body_layout().addStretch()
    return panel
