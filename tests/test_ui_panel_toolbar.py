"""Panel toolbar toggle testleri — sağ host üzerindeki ED/ET sekmeleri."""

from __future__ import annotations

from pathlib import Path

import pytest

from sdr_console.config.app_config import AppConfig
from sdr_console.ui.main_window import MainWindow


@pytest.fixture
def window(qtbot, tmp_config_path: Path) -> MainWindow:
    config = AppConfig.default()
    win = MainWindow(config=config, config_path=tmp_config_path)
    if hasattr(win._device, "realtime"):
        win._device.realtime = False
    qtbot.addWidget(win)
    return win


@pytest.fixture
def shown_window(window: MainWindow, qtbot) -> MainWindow:
    window.show()
    qtbot.waitExposed(window)
    return window


def test_panel_toolbar_has_toggle_for_each_dock(shown_window: MainWindow) -> None:
    texts = {box.text() for box in shown_window._panel_toolbar.checkboxes}

    assert "Tespit" in texts
    assert "Tarama" in texts
    assert "TX" in texts
    assert "DF" in texts
    assert "Karıştırma" in texts
    assert "RX" not in texts
    assert "Audio" not in texts


def test_toggle_action_hides_and_shows_panel(shown_window: MainWindow) -> None:
    action = shown_window._panel_toolbar.toggle_action_for("dock_scan")

    assert shown_window._scan_panel.isVisible()
    action.trigger()
    assert not shown_window._scan_panel.isVisible()
    action.trigger()
    assert shown_window._scan_panel.isVisible()


def test_checkbox_stays_in_sync_with_panel(shown_window: MainWindow) -> None:
    action = shown_window._panel_toolbar.toggle_action_for("dock_detection")
    checkbox = shown_window._panel_toolbar.checkbox_for("dock_detection")

    action.trigger()
    assert not checkbox.isChecked()
    assert not shown_window._detection_panel.isVisible()

    action.trigger()
    assert checkbox.isChecked()
    assert shown_window._detection_panel.isVisible()
