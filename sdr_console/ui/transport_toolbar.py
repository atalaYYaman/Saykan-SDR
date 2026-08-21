"""Main-window transport QToolBar (MASTER Tur B)."""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QToolBar,
    QWidget,
)

from sdr_console.hal.registry import DEVICE_CHOICES

ED_OFFLINE = "ED: Offline"
ED_ONLINE = "ED: Online"
ET_STANDBY = "ET: Standby"
ET_ARMED = "ET: Armed"
ET_ACTIVE = "ET: Active"
GNSS_EMPTY = "GNSS —"
MISSION_TIME_EMPTY = "--:--:--"


def _repolish(widget: QWidget) -> None:
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


class TransportToolBar(QToolBar):
    """Device / URI / Scan / Start / Stop plus SHELL status slots on the right."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Transport", parent)
        self.setObjectName("toolbar_main")
        self.setMovable(False)
        self.setFloatable(False)
        self.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)

        device_label = QLabel("Device:")
        self.device_combo = QComboBox()
        self.device_combo.setObjectName("transport_device")
        self.device_combo.setMinimumWidth(160)
        for device_id, label in DEVICE_CHOICES:
            self.device_combo.addItem(label, device_id)

        uri_label = QLabel("URI:")
        self.uri_edit = QLineEdit()
        self.uri_edit.setObjectName("transport_uri")
        self.uri_edit.setPlaceholderText("auto / ip:192.168.2.1 / usb:")
        self.uri_edit.setMinimumWidth(180)

        self.scan_button = QPushButton("Scan")
        self.scan_button.setObjectName("transport_scan")
        self.start_button = QPushButton("Start")
        self.start_button.setObjectName("transport_start")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("transport_stop")
        self.stop_button.setEnabled(False)

        self.addWidget(device_label)
        self.addWidget(self.device_combo)
        self.addWidget(uri_label)
        self.addWidget(self.uri_edit)
        self.addWidget(self.scan_button)
        self.addWidget(self.start_button)
        self.addWidget(self.stop_button)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        spacer.setObjectName("toolbar_spacer")
        self.addWidget(spacer)

        self.badge_ed = QLabel(ED_OFFLINE)
        self.badge_ed.setObjectName("badge_ed_subsystem")
        self.badge_ed.setToolTip("Elektronik Destek — Online yalnızca gerçek RX akışında")

        self.badge_et = QLabel(ET_STANDBY)
        self.badge_et.setObjectName("badge_et_subsystem")
        self.badge_et.setToolTip("Elektronik Taarruz — Active yalnızca gerçek TX iken")

        self.badge_gnss = QLabel(GNSS_EMPTY)
        self.badge_gnss.setObjectName("badge_gnss")
        self.badge_gnss.setToolTip("GNSS konum kaynağı yok")
        self.badge_gnss.setProperty("shell", "true")

        self.mission_time = QLabel(MISSION_TIME_EMPTY)
        self.mission_time.setObjectName("label_mission_time")
        self.mission_time.setToolTip("Yerel saat — GNSS zamanı bağlı değil")

        for badge in (
            self.badge_ed,
            self.badge_et,
            self.badge_gnss,
            self.mission_time,
        ):
            self.addWidget(badge)

        self.set_ed_online(False)
        self.set_et_state("standby")
        _repolish(self.badge_gnss)

        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._tick_mission_time)
        self._clock_timer.start()
        self._tick_mission_time()

    def _tick_mission_time(self) -> None:
        self.mission_time.setText(datetime.now().strftime("%H:%M:%S"))

    def set_ed_online(self, online: bool) -> None:
        """Online only when the RX pipeline is actually running."""
        if online:
            self.badge_ed.setText(ED_ONLINE)
            self.badge_ed.setProperty("state", "online")
            self.badge_ed.setProperty("shell", "false")
        else:
            self.badge_ed.setText(ED_OFFLINE)
            self.badge_ed.setProperty("state", "offline")
            self.badge_ed.setProperty("shell", "true")
        _repolish(self.badge_ed)

    def set_et_state(self, state: str) -> None:
        """standby | armed | active — active only during real TX."""
        normalized = state.lower()
        if normalized == "active":
            self.badge_et.setText(ET_ACTIVE)
            self.badge_et.setProperty("state", "active")
            self.badge_et.setProperty("shell", "false")
        elif normalized == "armed":
            self.badge_et.setText(ET_ARMED)
            self.badge_et.setProperty("state", "armed")
            self.badge_et.setProperty("shell", "false")
        else:
            self.badge_et.setText(ET_STANDBY)
            self.badge_et.setProperty("state", "standby")
            self.badge_et.setProperty("shell", "true")
        _repolish(self.badge_et)
