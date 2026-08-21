"""Collapsible group box for reclaiming vertical space in dense layouts."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGroupBox,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

_QWIDGETSIZE_MAX = 16777215
_COLLAPSED_TITLE_HEIGHT_PX = 32


class CollapsibleGroupBox(QGroupBox):
    """Panel whose body can be hidden, leaving a header button.

    Checked header = expanded. Does not use QGroupBox.setCheckable, which
    disables children and desyncs the title indicator from the body.
    """

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__("", parent)
        self._title_text = title
        self.setCheckable(False)
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )

        self._toggle = QToolButton(self)
        self._toggle.setObjectName("collapsible_header")
        self._toggle.setText(title)
        self._toggle.setCheckable(True)
        self._toggle.setChecked(True)
        self._toggle.setAutoRaise(True)
        self._toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._toggle.setArrowType(Qt.ArrowType.DownArrow)
        self._toggle.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self._toggle.toggled.connect(self._on_header_toggled)

        self._body = QWidget(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)
        outer.addWidget(self._toggle)
        outer.addWidget(self._body)

    def title(self) -> str:
        return self._title_text

    def setTitle(self, title: str) -> None:
        self._title_text = title
        toggle = getattr(self, "_toggle", None)
        if toggle is not None:
            toggle.setText(title)

    def header_button(self) -> QToolButton:
        return self._toggle

    def content_widget(self) -> QWidget:
        """Widget that should receive the panel's form/layout."""
        return self._body

    def is_expanded(self) -> bool:
        return self._toggle.isChecked()

    def set_expanded(self, expanded: bool) -> None:
        expanded = bool(expanded)
        if self._toggle.isChecked() == expanded:
            self._apply_expanded(expanded)
            return
        self._toggle.setChecked(expanded)

    def _on_header_toggled(self, expanded: bool) -> None:
        self._apply_expanded(expanded)
        self.toggled.emit(expanded)

    def _apply_expanded(self, expanded: bool) -> None:
        self._toggle.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
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
            title_height = max(
                self.minimumSizeHint().height(),
                _COLLAPSED_TITLE_HEIGHT_PX,
            )
            self.setMaximumHeight(title_height)
            self.setMinimumHeight(title_height)
        self.updateGeometry()
        parent = self.parentWidget()
        if parent is not None:
            parent.updateGeometry()
            ancestor = parent.parentWidget()
            if ancestor is not None:
                ancestor.updateGeometry()
