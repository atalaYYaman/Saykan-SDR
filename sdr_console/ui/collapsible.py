"""Collapsible group box for reclaiming vertical space in dense layouts."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QGroupBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

_QWIDGETSIZE_MAX = 16777215
_COLLAPSED_TITLE_HEIGHT_PX = 28


class CollapsibleGroupBox(QGroupBox):
    """QGroupBox whose body can be hidden, leaving only the title row.

    Uses the built-in checkable title control: checked = expanded.
    """

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self.setCheckable(True)
        self.setChecked(True)
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )

        self._body = QWidget(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 10, 8, 8)
        outer.setSpacing(6)
        outer.addWidget(self._body)

        self.toggled.connect(self._on_expanded_toggled)

    def content_widget(self) -> QWidget:
        """Widget that should receive the panel's form/layout."""
        return self._body

    def is_expanded(self) -> bool:
        return self.isChecked()

    def set_expanded(self, expanded: bool) -> None:
        self.setChecked(expanded)

    def _on_expanded_toggled(self, expanded: bool) -> None:
        self._body.setVisible(expanded)
        if expanded:
            self._body.setMaximumHeight(_QWIDGETSIZE_MAX)
            self.setMaximumHeight(_QWIDGETSIZE_MAX)
            self.setMinimumHeight(0)
            self.setSizePolicy(
                QSizePolicy.Policy.Preferred,
                QSizePolicy.Policy.Maximum,
            )
        else:
            self._body.setMaximumHeight(0)
            self.setSizePolicy(
                QSizePolicy.Policy.Preferred,
                QSizePolicy.Policy.Fixed,
            )
            title_height = max(self.minimumSizeHint().height(), _COLLAPSED_TITLE_HEIGHT_PX)
            self.setMaximumHeight(title_height)
            self.setMinimumHeight(title_height)
        self.updateGeometry()
        parent = self.parentWidget()
        if parent is not None:
            parent.updateGeometry()
            ancestor = parent.parentWidget()
            if ancestor is not None:
                ancestor.updateGeometry()
