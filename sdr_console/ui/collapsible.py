"""Collapsible group box for reclaiming vertical space in dense layouts."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QGroupBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

_QWIDGETSIZE_MAX = 16777215


class CollapsibleGroupBox(QGroupBox):
    """QGroupBox whose body can be hidden, leaving only the title row.

    Uses the built-in checkable title control: checked = expanded.
    """

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self.setCheckable(True)
        self.setChecked(True)
        self.setStyleSheet(
            "CollapsibleGroupBox {"
            " border: 1px solid palette(mid);"
            " border-radius: 4px;"
            " margin-top: 14px;"
            " padding-top: 4px;"
            "}"
            "CollapsibleGroupBox::title {"
            " subcontrol-origin: margin;"
            " subcontrol-position: top left;"
            " left: 10px;"
            " padding: 0 6px;"
            "}"
        )
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Preferred,
        )

        self._body = QWidget(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
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
            self.setMaximumHeight(_QWIDGETSIZE_MAX)
            self.setSizePolicy(
                QSizePolicy.Policy.Preferred,
                QSizePolicy.Policy.Preferred,
            )
        else:
            self.setSizePolicy(
                QSizePolicy.Policy.Preferred,
                QSizePolicy.Policy.Fixed,
            )
            # Title-only height after body is hidden.
            self.setMaximumHeight(max(self.minimumSizeHint().height(), 24))
        self.updateGeometry()
        parent = self.parentWidget()
        if parent is not None:
            parent.updateGeometry()
