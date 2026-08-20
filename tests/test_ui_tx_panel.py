"""TX test-sinyali paneli ve MainWindow bağlantı testleri."""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox

from sdr_console.config.app_config import AppConfig
from sdr_console.tx.constants import (
    DEFAULT_BURST_DURATION_S,
    DEFAULT_MAX_TX_DURATION_S,
    DEFAULT_TX_ATTENUATION_DB,
    DEFAULT_TX_INTERVAL_S,
    MIN_TX_ATTENUATION_DB,
)
from sdr_console.ui.main_window import MainWindow
from sdr_console.ui.tx_panel import DEFAULT_TX_FREQ_MHZ, TxPanel

pytest.importorskip("pytestqt")


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
    assert panel.duration_s() == pytest.approx(DEFAULT_BURST_DURATION_S)
    assert panel.interval_s() == pytest.approx(DEFAULT_TX_INTERVAL_S)
    assert panel._duration_spin.maximum() == pytest.approx(DEFAULT_MAX_TX_DURATION_S)
    assert not panel._stop_button.isEnabled()
    assert panel._oneshot_button.isEnabled()
    assert panel._loop_button.isEnabled()
    assert not panel.loopback_enabled()


def test_tx_panel_emits_oneshot_and_loop_signals(panel: TxPanel, qtbot) -> None:
    with qtbot.waitSignal(panel.oneshot_requested, timeout=1000):
        qtbot.mouseClick(panel._oneshot_button, Qt.MouseButton.LeftButton)
    with qtbot.waitSignal(panel.loop_requested, timeout=1000):
        qtbot.mouseClick(panel._loop_button, Qt.MouseButton.LeftButton)


def test_buttons_lock_while_transmitting(panel: TxPanel) -> None:
    panel.set_transmitting(True)
    assert not panel._oneshot_button.isEnabled()
    assert not panel._loop_button.isEnabled()
    assert panel._stop_button.isEnabled()


def test_oneshot_cancel_does_not_transmit(window: MainWindow, monkeypatch) -> None:
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.No,
    )
    window._tx_panel.oneshot_requested.emit()

    assert window._tx_device is None
    assert "iptal" in window._tx_panel._status_label.text().lower()


def test_oneshot_confirm_uses_mock_tx_and_snaps_rx(
    window: MainWindow,
    monkeypatch,
) -> None:
    window._tx_panel._duration_spin.setValue(0.20)
    window._tx_panel._freq_spin.setValue(433.97)

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    window._tx_panel.oneshot_requested.emit()

    assert window._tx_device is not None
    assert window._tx_device.transmitted_iq is not None
    assert window._tx_device.transmitted_iq.size > 0
    assert window._tx_panel.is_transmitting()
    assert window._tx_device.attenuation_db == pytest.approx(DEFAULT_TX_ATTENUATION_DB)
    assert window._center_freq_spin.value() == pytest.approx(433_970_000.0)
    assert window._device.center_freq_hz == pytest.approx(433_970_000.0)


def test_loop_transmits_again_after_interval(
    window: MainWindow,
    qtbot,
    monkeypatch,
) -> None:
    window._tx_panel._duration_spin.setValue(0.12)
    window._tx_panel._interval_spin.setValue(0.12)

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    window._tx_panel.loop_requested.emit()
    qtbot.waitUntil(lambda: window._tx_device is not None, timeout=2000)
    qtbot.waitUntil(
        lambda: window._tx_device is not None
        and len(getattr(window._tx_device, "history", [])) >= 2,
        timeout=5000,
    )
    assert window._tx_loop_active
    window._on_tx_stop_requested()
    assert not window._tx_loop_active
    assert window._tx_device is None


def test_duplex_hint_only_for_pluto(window: MainWindow) -> None:
    assert window._sample_rate_label.text() == "Sample rate"
    window._active_device_id = "pluto"
    window._sync_duplex_sample_rate_hint()
    text = window._sample_rate_label.text()
    assert text.startswith("Sample rate (")
    assert "eşzamanlı RX+TX" in text
    assert "2.048" in text
    assert "1.024" in text
