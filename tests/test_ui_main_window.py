"""pytest-qt tests for MainWindow start/stop and config isolation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PyQt6.QtCore import Qt

from sdr_console.config.app_config import AppConfig
from sdr_console.config.storage import load_config
from sdr_console.ui.main_window import MainWindow

pytest.importorskip("pytestqt")


@pytest.fixture
def window(qtbot, tmp_config_path: Path):
    config = AppConfig.default()
    win = MainWindow(config=config, config_path=tmp_config_path)
    if hasattr(win._device, "realtime"):
        win._device.realtime = False
    qtbot.addWidget(win)
    return win


def test_start_stop_toggles_controls(window: MainWindow, qtbot) -> None:
    assert window._start_button.isEnabled()
    assert not window._stop_button.isEnabled()

    qtbot.mouseClick(window._start_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window._pipeline.is_running, timeout=5000)
    assert not window._start_button.isEnabled()
    assert window._stop_button.isEnabled()

    qtbot.mouseClick(window._stop_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not window._pipeline.is_running, timeout=5000)
    assert window._start_button.isEnabled()


def test_close_event_writes_injected_config_path(
    window: MainWindow,
    tmp_config_path: Path,
) -> None:
    window._center_freq_spin.setValue(120_000_000.0)
    window.close()

    assert tmp_config_path.exists()
    loaded = load_config(tmp_config_path)
    assert loaded.center_freq_hz == 120_000_000.0


def test_plot_selection_moves_vfo_without_retuning_device(window: MainWindow) -> None:
    original_center_hz = window._device.center_freq_hz
    target_hz = original_center_hz + 300_000.0

    window._display.frequency_selected.emit(target_hz)

    assert window._channel.center_freq_hz == target_hz
    assert window._config.listen_freq_hz == target_hz
    assert window._device.center_freq_hz == original_center_hz
    assert window._vfo_label is not None
    assert "MHz" in window._vfo_label.text()


def test_out_of_band_selection_is_clamped_to_the_visible_span(window: MainWindow) -> None:
    center_hz = window._device.center_freq_hz
    band_high_hz = center_hz + window._device.sample_rate_hz / 2.0

    window._display.frequency_selected.emit(center_hz + 50_000_000.0)

    assert window._channel.high_hz == band_high_hz


def test_center_frequency_change_moves_the_display_axis(window: MainWindow) -> None:
    window._center_freq_spin.setValue(120_000_000.0)

    assert window._display.spectrum.center_freq_hz == 120_000_000.0
    assert window._channel.center_freq_hz == window._config.listen_freq_hz
    low_hz = 120_000_000.0 - window._device.sample_rate_hz / 2.0
    assert window._channel.center_freq_hz >= low_hz


def test_close_event_persists_listening_channel(
    window: MainWindow,
    tmp_config_path: Path,
) -> None:
    target_hz = window._device.center_freq_hz + 200_000.0
    window._display.frequency_selected.emit(target_hz)
    window.close()

    loaded = load_config(tmp_config_path)
    assert loaded.listen_freq_hz == target_hz
    assert loaded.channel_bandwidth_hz == window._channel.bandwidth_hz


def test_invalid_saved_config_does_not_crash(qtbot, tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"device_id": "nope", "fft_size": "x"}), encoding="utf-8")
    config = load_config(bad)
    win = MainWindow(config=config, config_path=tmp_path / "out.json")
    if hasattr(win._device, "realtime"):
        win._device.realtime = False
    qtbot.addWidget(win)
    assert win._device is not None
    win.close()
