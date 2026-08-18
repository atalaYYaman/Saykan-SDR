"""Özellik paneli yerleşimi — dikey bölme, gizleme ve merkez alan genişlemesi."""

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
    window.resize(1200, 900)
    window.show()
    qtbot.waitExposed(window)
    return window


def test_visible_feature_panels_share_the_right_column(shown_window: MainWindow) -> None:
    host = shown_window._feature_host
    assert host.isVisible()
    assert host.width() >= 280
    assert shown_window._detection_panel.isVisible()
    assert shown_window._scan_panel.isVisible()
    assert shown_window._tx_panel.isVisible()
    assert shown_window._detection_panel.height() > 40
    assert shown_window._scan_panel.height() > 40
    assert shown_window._tx_panel.height() > 40


def test_two_visible_panels_split_the_right_area(shown_window: MainWindow, qtbot) -> None:
    shown_window._panel_toolbar.toggle_action_for("dock_tx").trigger()
    qtbot.waitUntil(
        lambda: not shown_window._feature_host.is_panel_visible("dock_tx"),
        timeout=2000,
    )

    assert shown_window._detection_panel.isVisible()
    assert shown_window._scan_panel.isVisible()
    assert not shown_window._tx_panel.isVisible()
    assert shown_window._feature_host.isVisible()
    assert shown_window._detection_panel.height() > 40
    assert shown_window._scan_panel.height() > 40


def test_receiver_is_fixed_and_toggles_live_in_hover_drawer(
    shown_window: MainWindow,
) -> None:
    drawer = shown_window._hover_drawer
    assert shown_window._receiver_box.isVisible()
    assert shown_window._audio_box.isVisible()
    assert shown_window._display_box.isVisible()
    assert not drawer.isAncestorOf(shown_window._receiver_box)
    assert not drawer.isAncestorOf(shown_window._audio_box)
    assert not drawer.isAncestorOf(shown_window._display_box)
    assert drawer.isAncestorOf(shown_window._panel_toolbar)
    assert not drawer.is_expanded()


def test_hiding_all_panels_expands_central_display(shown_window: MainWindow, qtbot) -> None:
    width_with_host = shown_window._display.width()

    for name in shown_window._feature_host.panel_names():
        action = shown_window._panel_toolbar.toggle_action_for(name)
        if action.isChecked():
            action.trigger()

    qtbot.waitUntil(
        lambda: not shown_window._feature_host.isVisible(),
        timeout=2000,
    )
    assert shown_window._display.isVisible()
    assert shown_window._display.width() >= width_with_host


def test_reopening_panel_via_toolbar_restores_visibility(shown_window: MainWindow) -> None:
    action = shown_window._panel_toolbar.toggle_action_for("dock_scan")

    action.trigger()
    assert not shown_window._scan_panel.isVisible()

    action.trigger()
    assert shown_window._scan_panel.isVisible()


def test_all_registered_panels_have_toolbar_short_labels(shown_window: MainWindow) -> None:
    from sdr_console.ui.panel_toolbar import DOCK_SHORT_LABELS

    for name in shown_window._feature_host.panel_names():
        assert name in DOCK_SHORT_LABELS


def test_feature_host_sits_right_of_the_display(shown_window: MainWindow) -> None:
    assert shown_window._feature_host.x() > shown_window._display.x()
    assert shown_window._controls_scroll.x() < shown_window._display.x()
