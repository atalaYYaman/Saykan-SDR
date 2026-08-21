"""SHELL feature panels — empty-state only, no fake telemetry (MASTER §5)."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
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


def create_params_shell() -> ShellPanel:
    panel = ShellPanel("Parametre", "Tespit seçin")
    vfo = QLineEdit("—")
    bw = QLineEdit("—")
    extra = QLineEdit("—")
    form = QFormLayout()
    form.addRow("VFO", vfo)
    form.addRow("BW", bw)
    form.addRow("Mod / protokol / EKKT", extra)
    _disabled(vfo, bw, extra)
    holder = QWidget()
    holder.setLayout(form)
    panel.body_layout().addWidget(holder)
    panel.body_layout().addStretch()
    return panel


def create_ea_jam_shell() -> ShellPanel:
    panel = ShellPanel("Karıştırma", "Karıştırma modülü bağlı değil")
    jam_type = QComboBox()
    jam_type.addItems(["Tekli", "Çoklu", "Baraj"])
    start = QPushButton("Start")
    stop = QPushButton("Stop")
    lookthrough = QCheckBox("Komite penceresi / look-through")
    note = QLabel("Almaç gerekmez (sürekli). Arabakışlı kip almaç ister.")
    note.setWordWrap(True)
    _disabled(jam_type, start, stop, lookthrough)
    row = QWidget()
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.addWidget(jam_type)
    row_layout.addWidget(start)
    row_layout.addWidget(stop)
    panel.body_layout().addWidget(row)
    panel.body_layout().addWidget(lookthrough)
    panel.body_layout().addWidget(note)
    panel.body_layout().addStretch()
    return panel


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
