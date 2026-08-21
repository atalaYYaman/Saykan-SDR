"""Sağ host üzerindeki görünür ED / ET sekme şeridi (HoverDrawer yerine)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from sdr_console.ui.panel_ids import (
    DOCK_SHORT_LABELS,
    ED_PANEL_NAMES,
    ET_PANEL_NAMES,
)

if TYPE_CHECKING:
    from sdr_console.ui.feature_host import FeaturePanelHost


class PanelToolBar(QWidget):
    """Checkable text tabs for each feature panel — two rows: ED then ET."""

    def __init__(self, host: FeaturePanelHost, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("panel_toolbar")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self._host = host
        self._buttons: dict[str, QToolButton] = {}
        self._actions: dict[str, QAction] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 2)
        root.setSpacing(2)

        ed_row = QHBoxLayout()
        ed_row.setSpacing(4)
        ed_label = QLabel("ED")
        ed_label.setObjectName("panel_toolbar_ed_label")
        ed_row.addWidget(ed_label)
        self._fill_row(ed_row, ED_PANEL_NAMES)
        ed_row.addStretch()

        et_host = QWidget()
        et_host.setObjectName("group_et_host")
        et_row = QHBoxLayout(et_host)
        et_row.setContentsMargins(0, 2, 0, 0)
        et_row.setSpacing(4)
        et_label = QLabel("ET")
        et_label.setObjectName("panel_toolbar_et_label")
        et_row.addWidget(et_label)
        self._fill_row(et_row, ET_PANEL_NAMES)
        et_row.addStretch()

        root.addLayout(ed_row)
        root.addWidget(et_host)
        self.sync_from_host()

    def _fill_row(self, row: QHBoxLayout, names: tuple[str, ...]) -> None:
        host = self._host
        present = set(host.panel_names())
        for name in names:
            if name not in present:
                continue
            short = DOCK_SHORT_LABELS.get(name, name)
            action = QAction(short, self)
            action.setCheckable(True)
            action.setChecked(host.is_panel_visible(name))
            action.setToolTip(short)
            action.toggled.connect(self._make_action_handler(name))

            button = QToolButton()
            button.setObjectName(f"panel_tab_{name}")
            button.setCheckable(True)
            button.setText(short)
            button.setToolTip(short)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            button.setAutoRaise(True)
            self._bind_button(button, action)
            button.setChecked(action.isChecked())
            self._buttons[name] = button
            self._actions[name] = action
            row.addWidget(button)

    @property
    def checkboxes(self) -> list[QToolButton]:
        """Toggle buttons (name kept for existing tests)."""
        return list(self._buttons.values())

    def checkbox_for(self, name: str) -> QToolButton:
        return self._buttons[name]

    def toggle_action_for(self, name: str) -> QAction:
        return self._actions[name]

    def sync_from_host(self) -> None:
        """Match tab checked state to actually visible panels (no extra toggles)."""
        for name, action in self._actions.items():
            wanted = self._host.is_panel_visible(name)
            if action.isChecked() != wanted:
                action.blockSignals(True)
                action.setChecked(wanted)
                action.blockSignals(False)
            button = self._buttons[name]
            if button.isChecked() != wanted:
                button.blockSignals(True)
                button.setChecked(wanted)
                button.blockSignals(False)

    def _make_action_handler(self, name: str):
        def _on(checked: bool) -> None:
            self._host.set_panel_visible(name, checked)

        return _on

    def _bind_button(self, button: QToolButton, action: QAction) -> None:
        def on_button(checked: bool) -> None:
            if action.isChecked() != checked:
                action.setChecked(checked)

        def on_action(checked: bool) -> None:
            if button.isChecked() != checked:
                button.setChecked(checked)

        button.toggled.connect(on_button)
        action.toggled.connect(on_action)
