"""TX / Replay paneli ve MainWindow bağlantı testleri."""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox

from sdr_console.config.app_config import AppConfig
from sdr_console.tx.capture_decoder import analyze_capture
from sdr_console.tx.constants import DEFAULT_TX_ATTENUATION_DB, MIN_TX_ATTENUATION_DB
from sdr_console.tx.ook_encoder import encode_ook
from sdr_console.ui.main_window import MainWindow
from sdr_console.ui.tx_panel import DEFAULT_TX_FREQ_MHZ, TxPanel

pytest.importorskip("pytestqt")

SAMPLE_RATE_HZ = 2_000_000.0
BIT_DURATION_S = 0.0003


@pytest.fixture
def panel(qtbot) -> TxPanel:
    widget = TxPanel()
    qtbot.addWidget(widget)
    widget.show()
    return widget


@pytest.fixture
def window(qtbot, tmp_config_path: Path) -> MainWindow:
    config = AppConfig.default()
    win = MainWindow(config=config, config_path=tmp_config_path)
    if hasattr(win._device, "realtime"):
        win._device.realtime = False
    qtbot.addWidget(win)
    return win


def test_tx_panel_defaults(panel: TxPanel) -> None:
    assert panel.tx_freq_hz() == pytest.approx(DEFAULT_TX_FREQ_MHZ * 1_000_000.0)
    assert panel.attenuation_db() == pytest.approx(DEFAULT_TX_ATTENUATION_DB)
    assert panel.attenuation_db() >= MIN_TX_ATTENUATION_DB
    assert not panel.has_capture()
    assert not panel._replay_button.isEnabled()
    assert not panel._stop_button.isEnabled()
    assert panel._capture_button.isEnabled()


def test_tx_panel_emits_capture_and_replay_signals(panel: TxPanel, qtbot) -> None:
    with qtbot.waitSignal(panel.capture_requested, timeout=1000):
        qtbot.mouseClick(panel._capture_button, Qt.MouseButton.LeftButton)

    panel.set_has_capture(True)
    with qtbot.waitSignal(panel.replay_requested, timeout=1000):
        qtbot.mouseClick(panel._replay_button, Qt.MouseButton.LeftButton)


def test_replay_disabled_until_capture_and_while_busy(panel: TxPanel) -> None:
    assert not panel._replay_button.isEnabled()
    panel.set_has_capture(True)
    assert panel._replay_button.isEnabled()

    panel.set_busy(True)
    assert not panel._replay_button.isEnabled()
    assert not panel._capture_button.isEnabled()

    panel.set_busy(False)
    panel.set_transmitting(True)
    assert not panel._replay_button.isEnabled()
    assert panel._stop_button.isEnabled()


def test_capture_without_stream_shows_status(window: MainWindow) -> None:
    window._tx_panel.capture_requested.emit()
    assert "Start" in window._tx_panel._status_label.text()
    assert not window._tx_panel.has_capture()


def test_live_capture_from_mock_stream_enables_replay(
    window: MainWindow,
    qtbot,
) -> None:
    window._tx_panel._capture_duration_spin.setValue(0.05)
    qtbot.mouseClick(window._start_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window._pipeline.is_running, timeout=5000)

    window._tx_panel.capture_requested.emit()
    qtbot.waitUntil(lambda: window._tx_panel.has_capture(), timeout=5000)
    assert window._tx_panel._replay_button.isEnabled()
    assert window._tx_session.latest is not None


def test_replay_cancel_does_not_transmit(window: MainWindow, monkeypatch) -> None:
    iq = encode_ook([1, 0, 1], BIT_DURATION_S, SAMPLE_RATE_HZ, 0.85)
    window._tx_session.add_capture(analyze_capture(iq, SAMPLE_RATE_HZ, threshold=0.4))
    window._refresh_tx_panel_from_session()

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.No,
    )
    window._tx_panel.replay_requested.emit()

    assert window._tx_device is None
    assert "iptal" in window._tx_panel._status_label.text().lower()


def test_replay_confirm_uses_mock_tx(window: MainWindow, monkeypatch) -> None:
    iq = encode_ook([1, 0, 1, 1], BIT_DURATION_S, SAMPLE_RATE_HZ, 0.85)
    window._tx_session.add_capture(analyze_capture(iq, SAMPLE_RATE_HZ, threshold=0.4))
    window._refresh_tx_panel_from_session()
    window._tx_panel._max_duration_spin.setValue(0.20)

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    window._tx_panel.replay_requested.emit()

    assert window._tx_device is not None
    assert window._tx_device.transmitted_iq is not None
    assert window._tx_device.transmitted_iq.size > 0
    assert window._tx_panel.is_transmitting()
    assert window._tx_device.attenuation_db == pytest.approx(DEFAULT_TX_ATTENUATION_DB)
