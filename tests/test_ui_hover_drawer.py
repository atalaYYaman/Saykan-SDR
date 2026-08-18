"""HoverDrawer açılma / kapanma testleri."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QPointF
from PyQt6.QtGui import QEnterEvent
from PyQt6.QtWidgets import QApplication, QLabel

from sdr_console.ui.hover_drawer import (
    COLLAPSED_WIDTH_PX,
    EXPANDED_WIDTH_PX,
    HoverDrawer,
)


def test_hover_drawer_starts_collapsed(qtbot) -> None:
    drawer = HoverDrawer()
    qtbot.addWidget(drawer)
    drawer.show()
    qtbot.waitExposed(drawer)

    assert not drawer.is_expanded()
    assert drawer.width() == COLLAPSED_WIDTH_PX


def test_enter_event_expands_drawer(qtbot) -> None:
    drawer = HoverDrawer()
    drawer.add_panel(QLabel("Tespit"))
    qtbot.addWidget(drawer)
    drawer.show()
    qtbot.waitExposed(drawer)

    event = QEnterEvent(QPointF(4, 4), QPointF(4, 4), QPointF(4, 4))
    QApplication.sendEvent(drawer, event)

    assert drawer.is_expanded()
    assert drawer.width() == EXPANDED_WIDTH_PX


def test_leave_event_collapses_after_delay(qtbot) -> None:
    drawer = HoverDrawer()
    qtbot.addWidget(drawer)
    drawer.show()
    qtbot.waitExposed(drawer)
    drawer.expand()
    assert drawer.is_expanded()

    drawer.leaveEvent(QEvent(QEvent.Type.Leave))
    assert drawer._pointer_inside is False
    drawer._try_collapse()

    assert not drawer.is_expanded()
    assert drawer.width() == COLLAPSED_WIDTH_PX
