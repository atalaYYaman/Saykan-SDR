"""Özellik paneli yerleşimi — dikey bölme, gizleme ve merkez alan genişlemesi."""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtWidgets import QLabel, QScrollArea

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


def test_receiver_is_fixed_and_panel_tabs_live_on_the_host(
    shown_window: MainWindow,
) -> None:
    assert shown_window._receiver_box.isVisible()
    assert shown_window._audio_box.isVisible()
    assert shown_window._display_box.isVisible()
    assert shown_window._feature_host.isAncestorOf(shown_window._panel_toolbar)
    assert shown_window._panel_toolbar.isVisible()


def test_hiding_all_panels_keeps_tab_bar_so_they_can_reopen(
    shown_window: MainWindow, qtbot
) -> None:
    host = shown_window._feature_host
    assert host.isVisible()

    for name in host.panel_names():
        action = shown_window._panel_toolbar.toggle_action_for(name)
        if action.isChecked():
            action.trigger()

    qtbot.waitUntil(
        lambda: not host.is_panel_visible("dock_detection")
        and not host.is_panel_visible("dock_scan")
        and not host.is_panel_visible("dock_tx"),
        timeout=2000,
    )
    assert host.isVisible()
    assert shown_window._panel_toolbar.isVisible()
    empty = host.findChild(QLabel, "feature_host_empty")
    assert empty is not None and empty.isVisible()

    shown_window._panel_toolbar.toggle_action_for("dock_detection").trigger()
    qtbot.waitUntil(lambda: host.is_panel_visible("dock_detection"), timeout=2000)
    assert shown_window._detection_panel.isVisible()
    assert host.isVisible()


def test_reopening_panel_via_toolbar_restores_visibility(shown_window: MainWindow) -> None:
    action = shown_window._panel_toolbar.toggle_action_for("dock_scan")

    action.trigger()
    assert not shown_window._scan_panel.isVisible()

    action.trigger()
    assert shown_window._scan_panel.isVisible()


def test_all_registered_panels_have_toolbar_short_labels(shown_window: MainWindow) -> None:
    from sdr_console.ui.panel_ids import DOCK_SHORT_LABELS

    for name in shown_window._feature_host.panel_names():
        assert name in DOCK_SHORT_LABELS


def test_feature_host_sits_right_of_the_display(shown_window: MainWindow) -> None:
    assert shown_window._feature_host.x() > shown_window._display.x()
    assert shown_window._controls_scroll.y() < shown_window._display.y()


def test_receiver_audio_display_sit_side_by_side_above_waterfall(
    shown_window: MainWindow,
) -> None:
    assert shown_window._audio_box.x() > shown_window._receiver_box.x()
    assert shown_window._display_box.x() > shown_window._audio_box.x()
    assert shown_window._receiver_box.y() < shown_window._display.y()
    assert shown_window._audio_box.y() < shown_window._display.y()
    assert shown_window._display_box.y() < shown_window._display.y()

    waterfall = shown_window._display.waterfall
    spectrum = shown_window._display.spectrum
    assert waterfall.y() >= spectrum.y()
    assert waterfall.width() >= shown_window._display.width() - 8
    assert waterfall.width() > waterfall.height()


def test_hiding_a_panel_gives_remaining_panels_the_column(shown_window: MainWindow, qtbot) -> None:
    host = shown_window._feature_host

    shown_window._panel_toolbar.toggle_action_for("dock_detection").trigger()
    shown_window._panel_toolbar.toggle_action_for("dock_tx").trigger()
    qtbot.waitUntil(
        lambda: host.is_panel_visible("dock_scan")
        and not host.is_panel_visible("dock_detection")
        and not host.is_panel_visible("dock_tx"),
        timeout=2000,
    )

    assert host.isVisible()
    assert shown_window._scan_panel.isVisible()
    viewport_h = host.findChild(QScrollArea, "feature_host_scroll")
    assert viewport_h is not None
    assert shown_window._scan_panel.height() >= int(viewport_h.viewport().height() * 0.7)


def test_audio_and_receiver_controls_stay_inside_their_frames(
    shown_window: MainWindow,
) -> None:
    shown_window._audio_box.set_expanded(True)
    shown_window._display_box.set_expanded(True)
    audio_box = shown_window._audio_box
    for widget in (
        shown_window._audio_check,
        shown_window._demod_combo,
        shown_window._deemphasis_combo,
        shown_window._nfm_deemphasis_check,
        shown_window._afbw_combo,
        shown_window._agc_check,
        shown_window._agc_combo,
        shown_window._squelch_check,
        shown_window._squelch_spin,
        shown_window._volume_slider,
        shown_window._volume_spin,
    ):
        assert widget.isVisible()
        assert widget.width() > 0
        assert widget.height() > 0
        mapped = widget.mapTo(audio_box, widget.rect().topLeft())
        assert mapped.x() >= 0
        assert mapped.x() + widget.width() <= audio_box.width() + 2

    for widget in (
        shown_window._center_freq_spin,
        shown_window._listen_freq_spin,
        shown_window._gain_spin,
        shown_window._fft_size_combo,
        shown_window._bandwidth_combo,
        shown_window._vmin_spin,
        shown_window._vmax_spin,
    ):
        assert widget.isVisible()
        assert widget.width() > 0
