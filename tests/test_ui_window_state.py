"""MainWindow saveState / restoreState persistence tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from sdr_console.config.app_config import AppConfig
from sdr_console.config.storage import load_config
from sdr_console.ui.main_window import MainWindow


@pytest.fixture
def window(qtbot, tmp_config_path: Path) -> MainWindow:
    config = AppConfig.default()
    win = MainWindow(config=config, config_path=tmp_config_path)
    if hasattr(win._device, "realtime"):
        win._device.realtime = False
    qtbot.addWidget(win)
    return win


def test_close_event_persists_window_state(
    window: MainWindow,
    tmp_config_path: Path,
    qtbot,
) -> None:
    window.show()
    qtbot.waitExposed(window)
    window.close()

    loaded = load_config(tmp_config_path)
    assert loaded.window_state.strip() != ""


def test_stale_window_layout_is_not_restored(
    tmp_config_path: Path,
    qtbot,
) -> None:
    config = AppConfig.default()
    config.window_layout_version = 0
    config.window_state = "not-a-real-state"
    win = MainWindow(config=config, config_path=tmp_config_path)
    if hasattr(win._device, "realtime"):
        win._device.realtime = False
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    assert win._feature_host.isVisible()
    assert win._detection_panel.isVisible()
    assert win._scan_panel.isVisible()
    assert win._tx_panel.isVisible()
