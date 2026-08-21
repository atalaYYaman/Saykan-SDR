"""Tur A: Fusion + QPalette + QSS from design-system/MASTER.md."""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication, QToolBar, QWidget

from sdr_console.config.app_config import AppConfig
from sdr_console.ui.main_window import MainWindow
from sdr_console.ui.theme import (
    apply_application_theme,
    build_stylesheet,
    theme_is_applied,
)
from sdr_console.ui.theme.tokens import COLOR_BG_APP, COLOR_ED_ACCENT, COLOR_ET_ACCENT

pytest.importorskip("pytestqt")


@pytest.fixture
def window(qtbot, tmp_config_path: Path) -> MainWindow:
    win = MainWindow(config=AppConfig.default(), config_path=tmp_config_path)
    qtbot.addWidget(win)
    return win


def test_stylesheet_encodes_master_transport_colors() -> None:
    css = build_stylesheet()
    assert COLOR_ED_ACCENT in css
    assert COLOR_ET_ACCENT in css
    assert "transport_start" in css
    assert "transport_stop" in css
    assert "glass" not in css.lower()


def test_apply_theme_is_idempotent(qtbot) -> None:
    app = QApplication.instance()
    assert app is not None
    apply_application_theme(app)
    assert theme_is_applied(app)
    assert apply_application_theme(app) is False
    style_class = type(app.style()).__name__.lower()
    style_name = app.style().objectName().lower()
    assert "fusion" in style_class or "fusion" in style_name or bool(app.styleSheet())
    assert "transport_start" in app.styleSheet()
    window = app.palette().color(QPalette.ColorRole.Window)
    assert window.name().lower() == COLOR_BG_APP.lower()


def test_main_window_object_names_match_master(window: MainWindow) -> None:
    assert window._device_combo.objectName() == "transport_device"
    assert window._uri_edit.objectName() == "transport_uri"
    assert window._scan_button.objectName() == "transport_scan"
    assert window._start_button.objectName() == "transport_start"
    assert window._stop_button.objectName() == "transport_stop"
    assert window._receiver_box.objectName() == "group_receiver"
    assert window._audio_box.objectName() == "group_audio"
    assert window._display_box.objectName() == "group_display"
    assert window._controls_column.objectName() == "dock_left_controls"
    assert window._display.objectName() == "display_center"
    assert window._feature_host.objectName() == "feature_host"
    assert window._detection_panel.objectName() == "dock_detection"
    assert window._scan_panel.objectName() == "dock_scan"
    assert window._tx_panel.objectName() == "dock_tx"
    assert window._df_panel.objectName() == "dock_df"
    assert window._geoloc_panel.objectName() == "dock_geoloc"
    assert window._params_panel.objectName() == "dock_params"
    assert window._ea_jam_panel.objectName() == "dock_ea_jam"
    assert window._ea_deceive_panel.objectName() == "dock_ea_deceive"
    assert window._ea_gnss_panel.objectName() == "dock_ea_gnss"
    assert window._panel_toolbar.objectName() == "panel_toolbar"
    assert window.findChild(QWidget, "group_et_host") is not None
    assert window._status_label.objectName() == "status_bar"
    toolbar = window.findChild(QToolBar, "toolbar_main")
    assert toolbar is not None
    assert window._start_button.objectName() == "transport_start"
