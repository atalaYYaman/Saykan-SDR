"""Sağ özellik panelleri — açık olanlar dikey splitter ile aynı anda görünür."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QSizePolicy, QSplitter, QVBoxLayout, QWidget

FEATURE_HOST_MIN_WIDTH_PX = 300
FEATURE_HOST_MAX_WIDTH_PX = 440


class FeaturePanelHost(QWidget):
    """Tespit / Tarama / TX panellerini dikey böler; gizli olanlar yer kaplamaz."""

    visibility_changed = pyqtSignal()

    def __init__(
        self,
        panels: list[tuple[str, QWidget]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("feature_host")
        self.setMinimumWidth(FEATURE_HOST_MIN_WIDTH_PX)
        self.setMaximumWidth(FEATURE_HOST_MAX_WIDTH_PX)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        self._panels: dict[str, QWidget] = {}
        self._wanted: dict[str, bool] = {}
        self._splitter = QSplitter(Qt.Orientation.Vertical, self)
        self._splitter.setChildrenCollapsible(True)

        for name, widget in panels:
            widget.setObjectName(name)
            widget.setMaximumWidth(16777215)
            self._panels[name] = widget
            self._wanted[name] = True
            self._splitter.addWidget(widget)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._splitter)

        self.equalize()

    @property
    def splitter(self) -> QSplitter:
        return self._splitter

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
        self._panels[name].setVisible(visible)
        self.equalize()
        self.visibility_changed.emit()

    def equalize(self) -> None:
        """Açık paneller yüksekliği eşit paylaşsın; hiçbiri yoksa host gizlensin."""
        any_visible = any(self._wanted.values())
        self.setVisible(any_visible)
        if not any_visible:
            return
        sizes = [1000 if self._wanted[name] else 0 for name in self._panels]
        self._splitter.setSizes(sizes)
