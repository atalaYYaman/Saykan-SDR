"""SHELL empty-state panels — no fake telemetry."""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtWidgets import QComboBox, QLineEdit

from sdr_console.config.app_config import AppConfig
from sdr_console.ui.main_window import MainWindow
from sdr_console.ui.shell_panel import ShellPanel

pytest.importorskip("pytestqt")


@pytest.fixture
def window(qtbot, tmp_config_path: Path) -> MainWindow:
    win = MainWindow(config=AppConfig.default(), config_path=tmp_config_path)
    qtbot.addWidget(win)
    return win


def test_shell_panels_start_hidden_with_empty_copy(window: MainWindow) -> None:
    assert isinstance(window._df_panel, ShellPanel)
    assert window._df_panel.empty_text() == "DF bağlı değil"
    assert window._geoloc_panel.empty_text() == "Konum kaynağı yok"
    assert window._params_panel.empty_text() == "Tespit seçin"
    assert window._ea_jam_panel.empty_text() == "Karıştırma modülü bağlı değil"
    assert window._ea_deceive_panel.empty_text() == "Aldatma modülü bağlı değil"
    assert window._ea_gnss_panel.empty_text() == "GNSS aldatma bağlı değil"
    assert not window._df_panel.isVisible()
    assert not window._ea_gnss_panel.isVisible()


def test_opening_df_tab_shows_empty_state_not_fake_bearing(
    window: MainWindow, qtbot
) -> None:
    window.show()
    qtbot.waitExposed(window)
    action = window._panel_toolbar.toggle_action_for("dock_df")
    assert not action.isChecked()
    action.trigger()
    qtbot.waitUntil(lambda: window._df_panel.isVisible(), timeout=2000)
    assert "DF bağlı değil" in window._df_panel.empty_text()
    combos = window._df_panel.findChildren(QComboBox)
    assert combos
    assert all(not combo.isEnabled() for combo in combos)
    assert all(not field.isEnabled() for field in window._df_panel.findChildren(QLineEdit))
