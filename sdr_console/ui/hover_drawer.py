"""Hover ile açılıp kapanan sol panel çekmecesi."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtGui import QEnterEvent
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

COLLAPSED_WIDTH_PX = 24
EXPANDED_WIDTH_PX = 160
HIDE_DELAY_MS = 400


class HoverDrawer(QWidget):
    """İnce şerit; mouse gelince içerik açılır, bölgeden çıkınca kapanır."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        rail_label: str = "☰",
    ) -> None:
        super().__init__(parent)
        self.setObjectName("hover_drawer")
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        self._rail = QFrame(self)
        self._rail.setObjectName("hover_drawer_rail")
        self._rail.setFixedWidth(COLLAPSED_WIDTH_PX)
        self._rail.setMouseTracking(True)
        self._rail.setStyleSheet(
            "QFrame#hover_drawer_rail {"
            " background: palette(mid);"
            " border-right: 1px solid palette(dark);"
            "}"
        )

        rail_layout = QVBoxLayout(self._rail)
        rail_layout.setContentsMargins(0, 12, 0, 12)
        rail_layout.setSpacing(0)
        handle = QLabel(rail_label)
        handle.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        handle.setToolTip("Tespit / Tarama / TX — üzerine gelince açılır")
        rail_layout.addWidget(handle)
        rail_layout.addStretch()

        self._content = QWidget(self)
        self._content.setObjectName("hover_drawer_content")
        self._content.setMouseTracking(True)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(8, 8, 8, 8)
        self._content_layout.setSpacing(8)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setWidget(self._content)
        self._scroll.setVisible(False)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(self._rail)
        row.addWidget(self._scroll, stretch=1)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(HIDE_DELAY_MS)
        self._hide_timer.timeout.connect(self._try_collapse)

        self._expanded = False
        self._pointer_inside = False
        self._apply_collapsed()

    @property
    def rail(self) -> QFrame:
        return self._rail

    def content_layout(self) -> QVBoxLayout:
        """Toggle butonlarının ekleneceği yerleşim."""
        return self._content_layout

    def is_expanded(self) -> bool:
        return self._expanded

    def add_panel(self, panel: QWidget) -> None:
        self._content_layout.addWidget(panel)

    def expand(self) -> None:
        self._hide_timer.stop()
        if self._expanded:
            return
        self._expanded = True
        self._scroll.setVisible(True)
        self._rail.setVisible(False)
        self.setFixedWidth(EXPANDED_WIDTH_PX)

    def collapse(self) -> None:
        self._hide_timer.stop()
        if not self._expanded:
            return
        self._expanded = False
        self._apply_collapsed()

    def enterEvent(self, event: QEnterEvent) -> None:  # noqa: N802 — Qt API
        self._pointer_inside = True
        self.expand()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802 — Qt API
        self._pointer_inside = False
        self._hide_timer.start()
        super().leaveEvent(event)

    def _try_collapse(self) -> None:
        if self._should_stay_open():
            self._hide_timer.start()
            return
        self.collapse()

    def _should_stay_open(self) -> bool:
        if self._drawer_owns_popup():
            return True
        return self._pointer_inside

    def _drawer_owns_popup(self) -> bool:
        app = QApplication.instance()
        if app is None:
            return False
        popup = app.activePopupWidget()
        if popup is None:
            return False
        parent = popup.parentWidget()
        while parent is not None:
            if parent is self:
                return True
            parent = parent.parentWidget()
        return False

    def _apply_collapsed(self) -> None:
        self._scroll.setVisible(False)
        self._rail.setVisible(True)
        self.setFixedWidth(COLLAPSED_WIDTH_PX)
