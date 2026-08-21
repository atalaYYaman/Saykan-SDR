"""Sağ özellik panelleri — ED/ET sekme şeridi her zaman görünür kalır."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from sdr_console.ui.panel_toolbar import PanelToolBar

FEATURE_HOST_MIN_WIDTH_PX = 300
FEATURE_HOST_MAX_WIDTH_PX = 440
FEATURE_PANEL_MIN_HEIGHT_PX = 180
_QWIDGETSIZE_MAX = 16777215

PanelSpec = tuple[str, QWidget] | tuple[str, QWidget, bool]


class FeaturePanelHost(QWidget):
    """ED/ET sekme şeridi + kaydırılabilir açık paneller.

    İçerik panelleri kapanınca host gizlenmez; sekmelerden yeniden açılır.
    """

    visibility_changed = pyqtSignal()

    def __init__(
        self,
        panels: list[PanelSpec],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("feature_host")
        self.setMinimumWidth(FEATURE_HOST_MIN_WIDTH_PX)
        self.setMaximumWidth(FEATURE_HOST_MAX_WIDTH_PX)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        self._panels: dict[str, QWidget] = {}
        self._wanted: dict[str, bool] = {}

        self._body = QWidget()
        self._body.setObjectName("feature_host_body")
        self._body.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._column = QVBoxLayout(self._body)
        self._column.setContentsMargins(0, 0, 0, 0)
        self._column.setSpacing(8)

        for spec in panels:
            name, widget, default_visible = _parse_panel_spec(spec)
            widget.setObjectName(name)
            widget.setMinimumWidth(0)
            widget.setMaximumWidth(_QWIDGETSIZE_MAX)
            widget.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding,
            )
            self._panels[name] = widget
            self._wanted[name] = default_visible
            self._column.addWidget(widget, stretch=1)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("feature_host_scroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setWidget(self._body)

        self._empty = QLabel("Bir ED veya ET paneli seçin")
        self._empty.setObjectName("feature_host_empty")
        self._empty.setWordWrap(True)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self._tab_bar = PanelToolBar(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(0)
        layout.addWidget(self._tab_bar)
        layout.addWidget(self._empty, stretch=1)
        layout.addWidget(self._scroll, stretch=1)

        self.equalize()

    @property
    def tab_bar(self) -> PanelToolBar:
        return self._tab_bar

    def panel_names(self) -> list[str]:
        return list(self._panels.keys())

    def panel(self, name: str) -> QWidget:
        return self._panels[name]

    def is_panel_visible(self, name: str) -> bool:
        return self._wanted[name]

    def set_panel_visible(self, name: str, visible: bool) -> None:
        visible = bool(visible)
        if self._wanted[name] == visible:
            return
        self._wanted[name] = visible
        self.equalize()
        self.visibility_changed.emit()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.equalize()

    def equalize(self) -> None:
        """Açık panelleri göster; hiçbiri yoksa boş durum + sekmeler kalsın."""
        self.setMinimumWidth(FEATURE_HOST_MIN_WIDTH_PX)
        self.setMaximumWidth(FEATURE_HOST_MAX_WIDTH_PX)
        self.setVisible(True)

        visible_names = [name for name, wanted in self._wanted.items() if wanted]
        self._empty.setVisible(not visible_names)
        self._scroll.setVisible(bool(visible_names))

        min_total = 0
        for name, widget in self._panels.items():
            wanted = self._wanted[name]
            widget.setVisible(wanted)
            stretch = 1 if wanted else 0
            index = self._column.indexOf(widget)
            if index >= 0:
                self._column.setStretch(index, stretch)
            if not wanted:
                widget.setMinimumHeight(0)
                widget.setMaximumHeight(0)
                continue
            widget.setMaximumHeight(_QWIDGETSIZE_MAX)
            if len(visible_names) == 1:
                viewport_h = self._scroll.viewport().height()
                widget.setMinimumHeight(
                    viewport_h if viewport_h > 0 else 0
                )
            else:
                hint = max(widget.minimumSizeHint().height(), FEATURE_PANEL_MIN_HEIGHT_PX)
                widget.setMinimumHeight(hint)
                min_total += hint

        self._body.setMinimumHeight(min_total)
        self.updateGeometry()
        parent = self.parentWidget()
        if parent is not None:
            parent.updateGeometry()
            layout = parent.layout()
            if layout is not None:
                layout.activate()


def _parse_panel_spec(spec: PanelSpec) -> tuple[str, QWidget, bool]:
    if len(spec) == 3:
        name, widget, default_visible = spec
        return name, widget, bool(default_visible)
    name, widget = spec
    return name, widget, True
