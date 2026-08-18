"""Sol hover çekmecesindeki dock görünürlük toggle'ları."""

from __future__ import annotations

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QCheckBox, QSizePolicy, QVBoxLayout, QWidget

from sdr_console.ui.feature_host import FeaturePanelHost

# Panel objectName → kısa toolbar etiketi (yeni panel eklerken buraya da ekleyin)
DOCK_SHORT_LABELS: dict[str, str] = {
    "dock_detection": "Tespit",
    "dock_scan": "Tarama",
    "dock_tx": "TX",
    # Gelecek paneller (UI eklendiğinde aktif edin):
    # "dock_map": "Harita",
}


class PanelToolBar(QWidget):
    """Tespit / Tarama / TX görünürlük kutuları — HoverDrawer içeriği."""

    def __init__(self, host: FeaturePanelHost, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("panel_toolbar")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self._host = host

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)

        self._checkboxes: dict[str, QCheckBox] = {}
        self._actions: dict[str, QAction] = {}
        for name in host.panel_names():
            short = DOCK_SHORT_LABELS.get(name, name)
            action = QAction(short, self)
            action.setCheckable(True)
            action.setChecked(host.is_panel_visible(name))
            action.setToolTip(short)
            action.toggled.connect(self._make_action_handler(name))

            checkbox = QCheckBox(short)
            checkbox.setToolTip(short)
            checkbox.setChecked(action.isChecked())
            self._bind_checkbox(checkbox, action)
            self._checkboxes[name] = checkbox
            self._actions[name] = action
            layout.addWidget(checkbox)

        layout.addStretch()

    @property
    def checkboxes(self) -> list[QCheckBox]:
        return list(self._checkboxes.values())

    def checkbox_for(self, name: str) -> QCheckBox:
        return self._checkboxes[name]

    def toggle_action_for(self, name: str) -> QAction:
        return self._actions[name]

    def _make_action_handler(self, name: str):
        def _on(checked: bool) -> None:
            self._host.set_panel_visible(name, checked)

        return _on

    def _bind_checkbox(self, checkbox: QCheckBox, action: QAction) -> None:
        def on_box(checked: bool) -> None:
            if action.isChecked() != checked:
                action.setChecked(checked)

        def on_action(checked: bool) -> None:
            if checkbox.isChecked() != checked:
                checkbox.setChecked(checked)

        checkbox.toggled.connect(on_box)
        action.toggled.connect(on_action)
