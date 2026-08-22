"""Baraj karıştırma paneli ve MainWindow bağlantısı."""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog

from sdr_console.config.app_config import AppConfig
from sdr_console.detect.identified import IdentifiedPeak
from sdr_console.ea.constants import (
    DEFAULT_JAM_ATTENUATION_DB,
    DEFAULT_JAM_BANDWIDTH_HZ,
    DEFAULT_JAM_DURATION_S,
    MAX_JAM_DURATION_S,
    MIN_JAM_ATTENUATION_DB,
)
from sdr_console.tx.constants import MIN_TX_ATTENUATION_DB
from sdr_console.ui.ea_confirm_dialog import EaConfirmDialog
from sdr_console.ui.jam_panel import DEFAULT_JAM_FREQ_MHZ, JamPanel
from sdr_console.ui.main_window import MainWindow
from sdr_console.ui.shell_panel import ShellPanel

pytest.importorskip("pytestqt")


@pytest.fixture
def panel(qtbot) -> JamPanel:
    widget = JamPanel()
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


def test_jam_panel_defaults_lock_barrage(panel: JamPanel) -> None:
    assert panel.note_text() == "Baraj demosu — onaylı kısa yayın"
    assert panel.jam_type_text() == "Baraj"
    assert not panel._type_combo.isEnabled()
    assert not panel._lookthrough.isEnabled()
    assert not panel.lookthrough_enabled()
    assert panel.tx_freq_hz() == pytest.approx(DEFAULT_JAM_FREQ_MHZ * 1_000_000.0)
    assert panel.bandwidth_hz() == pytest.approx(DEFAULT_JAM_BANDWIDTH_HZ)
    assert panel.attenuation_db() == pytest.approx(DEFAULT_JAM_ATTENUATION_DB)
    assert panel.attenuation_db() >= MIN_JAM_ATTENUATION_DB
    assert panel._attenuation_spin.minimum() == pytest.approx(MIN_JAM_ATTENUATION_DB)
    assert panel._duration_spin.maximum() == pytest.approx(MAX_JAM_DURATION_S)
    assert panel.duration_s() == pytest.approx(DEFAULT_JAM_DURATION_S)
    assert not panel._stop_button.isEnabled()
    assert panel._start_button.isEnabled()
    assert not panel.loopback_enabled()


def test_jam_panel_emits_start_and_stop(panel: JamPanel, qtbot) -> None:
    with qtbot.waitSignal(panel.start_requested, timeout=1000):
        qtbot.mouseClick(panel._start_button, Qt.MouseButton.LeftButton)
    panel.set_transmitting(True)
    with qtbot.waitSignal(panel.stop_requested, timeout=1000):
        qtbot.mouseClick(panel._stop_button, Qt.MouseButton.LeftButton)


def test_confirm_ok_disabled_until_authorized(qtbot) -> None:
    dialog = EaConfirmDialog(
        freq_hz=433_970_000.0,
        bandwidth_hz=2_048_000.0,
        duration_s=5.0,
        attenuation_db=10.0,
    )
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog._ok is not None
    assert not dialog._ok.isEnabled()
    dialog._authorized.setChecked(True)
    assert dialog._ok.isEnabled()
    assert dialog.authorized_window()


def test_jam_cancel_does_not_transmit(window: MainWindow, monkeypatch) -> None:
    monkeypatch.setattr(EaConfirmDialog, "ask", staticmethod(lambda **kwargs: False))
    window._ea_jam_panel.start_requested.emit()
    assert window._tx_device is None
    assert not window._jam_session.is_active
    assert "iptal" in window._ea_jam_panel._status_label.text().lower()


def test_jam_confirm_uses_mock_tx_and_overlay(
    window: MainWindow,
    monkeypatch,
) -> None:
    window._ea_jam_panel._duration_spin.setValue(0.20)
    window._ea_jam_panel._freq_spin.setValue(433.97)
    window._ea_jam_panel._attenuation_spin.setValue(MIN_JAM_ATTENUATION_DB)

    monkeypatch.setattr(EaConfirmDialog, "ask", staticmethod(lambda **kwargs: True))
    window._ea_jam_panel.start_requested.emit()

    assert window._tx_device is not None
    assert window._tx_device.transmitted_iq is not None
    assert window._tx_device.attenuation_db == pytest.approx(MIN_JAM_ATTENUATION_DB)
    assert window._ea_jam_panel.is_transmitting()
    assert window._jam_session.is_active
    for overlay in window._display._jam_overlays:
        assert overlay.region.isVisible()
        low_hz, high_hz = overlay.region.getRegion()
        assert high_hz - low_hz == pytest.approx(window._ea_jam_panel.bandwidth_hz())

    window._on_jam_stop_requested()
    assert not window._jam_session.is_active
    assert window._tx_device is None
    for overlay in window._display._jam_overlays:
        assert not overlay.region.isVisible()


def test_jam_and_tx_are_mutually_exclusive(
    window: MainWindow,
    monkeypatch,
) -> None:
    from PyQt6.QtWidgets import QMessageBox

    window._tx_panel._duration_spin.setValue(0.20)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    window._tx_panel.oneshot_requested.emit()
    assert window._tx_panel.is_transmitting()

    monkeypatch.setattr(EaConfirmDialog, "ask", staticmethod(lambda **kwargs: True))
    window._ea_jam_panel.start_requested.emit()
    assert "TX/Test" in window._ea_jam_panel._status_label.text()
    assert not window._jam_session.is_active
    window._on_tx_stop_requested()


def test_copy_detection_sets_frequency(window: MainWindow) -> None:
    window._detection_panel.update_peaks(
        [
            IdentifiedPeak(
                name="A",
                frequency_hz=2_450_000_000.0,
                power_db=-20.0,
                capture_gain_db=20.0,
                detection_count=1,
            )
        ]
    )
    window._detection_panel._table.selectRow(0)
    window._ea_jam_panel.copy_detection_requested.emit()
    assert window._ea_jam_panel.tx_freq_hz() == pytest.approx(2_450_000_000.0)


def test_tx_panel_floor_unchanged(window: MainWindow) -> None:
    assert window._tx_panel._attenuation_spin.minimum() == pytest.approx(
        MIN_TX_ATTENUATION_DB
    )
    assert not isinstance(window._ea_jam_panel, ShellPanel)


def test_confirm_ask_false_on_reject(monkeypatch, qtbot) -> None:
    monkeypatch.setattr(EaConfirmDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    assert not EaConfirmDialog.ask(
        freq_hz=1.0,
        bandwidth_hz=200_000.0,
        duration_s=1.0,
        attenuation_db=10.0,
    )
