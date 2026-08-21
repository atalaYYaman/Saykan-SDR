"""Tur B: QToolBar transport + SHELL status badges."""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QToolBar

from sdr_console.config.app_config import AppConfig
from sdr_console.ui.main_window import MainWindow
from sdr_console.ui.transport_toolbar import ED_OFFLINE, ED_ONLINE, ET_STANDBY, GNSS_EMPTY

pytest.importorskip("pytestqt")


@pytest.fixture
def window(qtbot, tmp_config_path: Path) -> MainWindow:
    win = MainWindow(config=AppConfig.default(), config_path=tmp_config_path)
    if hasattr(win._device, "realtime"):
        win._device.realtime = False
    qtbot.addWidget(win)
    return win


def test_transport_is_a_locked_top_toolbar(window: MainWindow) -> None:
    toolbar = window.findChild(QToolBar, "toolbar_main")
    assert toolbar is not None
    assert toolbar is window._transport_toolbar
    assert not toolbar.isMovable()
    assert not toolbar.isFloatable()
    assert window._start_button.objectName() == "transport_start"
    assert window._stop_button.objectName() == "transport_stop"
    assert window._scan_button.objectName() == "transport_scan"


def test_shell_badges_start_empty_or_offline(window: MainWindow) -> None:
    toolbar = window._transport_toolbar
    assert toolbar.badge_ed.text() == ED_OFFLINE
    assert toolbar.badge_et.text() == ET_STANDBY
    assert toolbar.badge_gnss.text() == GNSS_EMPTY
    assert toolbar.badge_gnss.property("shell") == "true"
    assert ":" in toolbar.mission_time.text()


def test_ed_badge_follows_real_rx(window: MainWindow, qtbot) -> None:
    toolbar = window._transport_toolbar
    assert toolbar.badge_ed.text() == ED_OFFLINE
    qtbot.mouseClick(window._start_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window._pipeline.is_running, timeout=3000)
    assert toolbar.badge_ed.text() == ED_ONLINE
    qtbot.mouseClick(window._stop_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not window._pipeline.is_running, timeout=3000)
    assert toolbar.badge_ed.text() == ED_OFFLINE
