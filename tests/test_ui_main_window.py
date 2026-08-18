"""pytest-qt tests for MainWindow start/stop and config isolation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PyQt6.QtCore import Qt

from sdr_console.audio.sink import NullAudioSink
from sdr_console.config.app_config import AppConfig
from sdr_console.config.storage import load_config
from sdr_console.ui import main_window as main_window_module
from sdr_console.ui.main_window import MainWindow

pytest.importorskip("pytestqt")


def _use_fake_audio_sink(monkeypatch: pytest.MonkeyPatch) -> list[NullAudioSink]:
    """Make the window build audio chains that never open the sound card."""
    sinks: list[NullAudioSink] = []
    real_chain = main_window_module.AudioChain

    def sink_factory(rate_hz: float, queue) -> NullAudioSink:
        sink = NullAudioSink(rate_hz, queue)
        sinks.append(sink)
        return sink

    def build_chain(**kwargs):
        return real_chain(sink_factory=sink_factory, **kwargs)

    monkeypatch.setattr(main_window_module, "AudioChain", build_chain)
    return sinks


def _type_bandwidth(window: MainWindow, text: str) -> None:
    """Enter a custom bandwidth the way a user would: type, then leave the field."""
    line_edit = window._bandwidth_combo.lineEdit()
    assert line_edit is not None
    window._bandwidth_combo.setEditText(text)
    line_edit.editingFinished.emit()


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
    assert window._listen_freq_spin.value() == target_hz
    assert window._device.center_freq_hz == original_center_hz
    assert window._listen_freq_spin.value() == target_hz


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


def test_bandwidth_preset_resizes_the_overlay_box(window: MainWindow) -> None:
    index = window._bandwidth_combo.findData(125_000.0)
    window._bandwidth_combo.setCurrentIndex(index)

    assert window._channel.bandwidth_hz == 125_000.0
    assert window._config.channel_bandwidth_hz == 125_000.0
    low_hz, high_hz = window._display._overlays[0].region.getRegion()
    assert high_hz - low_hz == pytest.approx(125_000.0)


def test_custom_bandwidth_is_read_as_kilohertz(window: MainWindow) -> None:
    _type_bandwidth(window, "42.5 kHz")

    assert window._channel.bandwidth_hz == pytest.approx(42_500.0)
    low_hz, high_hz = window._display._overlays[1].region.getRegion()
    assert high_hz - low_hz == pytest.approx(42_500.0)


def test_invalid_bandwidth_text_is_rejected_and_reverted(window: MainWindow) -> None:
    original_bandwidth_hz = window._channel.bandwidth_hz

    _type_bandwidth(window, "not a number")

    assert window._channel.bandwidth_hz == original_bandwidth_hz
    assert "kHz" in window._status_label.text()
    assert "kHz" in window._bandwidth_combo.currentText()


def test_bandwidth_wider_than_the_band_is_clamped(window: MainWindow) -> None:
    _type_bandwidth(window, "999999 kHz")

    assert window._channel.bandwidth_hz == pytest.approx(window._device.sample_rate_hz)
    assert "2048" in window._bandwidth_combo.currentText()


def test_vfo_label_reports_the_resulting_if_rate(window: MainWindow) -> None:
    index = window._bandwidth_combo.findData(200_000.0)
    window._bandwidth_combo.setCurrentIndex(index)

    assert window._vfo_label is not None
    text = window._vfo_label.text()
    assert "BW 200.000 kHz" in text
    assert "IF 204.800 kHz" in text
    assert "dec 10" in text
    assert "AM" in text


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


def test_audio_toggle_while_idle_waits_for_the_stream(window: MainWindow) -> None:
    window._audio_check.setChecked(True)

    assert window._audio_requested
    assert window._audio_chain is None
    assert "stream" in window._status_label.text().lower()


def test_volume_slider_updates_config_and_spin(window: MainWindow) -> None:
    window._volume_slider.setValue(35)

    assert window._config.audio_volume == pytest.approx(0.35)
    assert window._volume_spin.value() == 35


def test_volume_spin_updates_slider_and_config(window: MainWindow) -> None:
    window._volume_spin.setValue(62)

    assert window._volume_slider.value() == 62
    assert window._config.audio_volume == pytest.approx(0.62)


def test_freq_step_combo_updates_spin_steps(window: MainWindow) -> None:
    index = window._freq_step_combo.findData(10_000.0)
    window._freq_step_combo.setCurrentIndex(index)

    assert window._config.freq_step_hz == 10_000.0
    assert window._center_freq_spin.singleStep() == 10_000.0
    assert window._listen_freq_spin.singleStep() == 10_000.0


def test_gain_step_combo_updates_gain_spin(window: MainWindow) -> None:
    index = window._gain_step_combo.findData(3.0)
    window._gain_step_combo.setCurrentIndex(index)

    assert window._config.gain_step_db == 3.0
    assert window._gain_spin.singleStep() == 3.0


def test_listen_freq_spin_moves_the_channel(window: MainWindow) -> None:
    target_hz = window._device.center_freq_hz + 250_000.0
    window._listen_freq_spin.setValue(target_hz)

    assert window._channel.center_freq_hz == target_hz
    assert window._config.listen_freq_hz == target_hz


@pytest.mark.parametrize(
    ("mode", "bandwidth_hz", "afbw_hz", "agc_preset"),
    [
        ("AM", 10_000.0, 4_000.0, "slow"),
        ("N-FM", 12_500.0, 4_000.0, "limiter"),
        ("W-FM", 200_000.0, 15_000.0, "limiter"),
        ("USB", 2_700.0, 3_000.0, "hang"),
        ("LSB", 2_700.0, 3_000.0, "hang"),
        ("CW", 500.0, 1_000.0, "fast"),
    ],
)
def test_demod_mode_switch_sets_default_bandwidth(
    window: MainWindow,
    mode: str,
    bandwidth_hz: float,
    afbw_hz: float,
    agc_preset: str,
) -> None:
    index = window._demod_combo.findData(mode)
    window._demod_combo.setCurrentIndex(index)

    assert window._config.demod_mode == mode
    assert window._channel.bandwidth_hz == bandwidth_hz
    assert window._config.channel_bandwidth_hz == bandwidth_hz
    assert window._config.afbw_hz == afbw_hz
    assert window._config.agc_enabled is True
    assert window._config.agc_preset == agc_preset
    assert mode in window._vfo_label.text()
    low_hz, high_hz = window._display._overlays[0].region.getRegion()
    assert high_hz - low_hz == pytest.approx(bandwidth_hz)
    # Mode defaults that are also presets should land on a combo item.
    if window._bandwidth_combo.findData(bandwidth_hz) >= 0:
        assert window._bandwidth_combo.currentData() == pytest.approx(bandwidth_hz)
    if window._afbw_combo.findData(afbw_hz) >= 0:
        assert window._afbw_combo.currentData() == pytest.approx(afbw_hz)
    assert window._agc_combo.currentData() == agc_preset
    assert window._agc_check.isChecked() is True


def test_demod_mode_reaches_audio_chain_while_streaming(
    window: MainWindow,
    qtbot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_fake_audio_sink(monkeypatch)
    window._audio_check.setChecked(True)
    qtbot.mouseClick(window._start_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window._audio_chain is not None, timeout=5000)

    index = window._demod_combo.findData("USB")
    window._demod_combo.setCurrentIndex(index)

    chain = window._audio_chain
    assert chain is not None
    qtbot.waitUntil(
        lambda: chain.worker.demodulator is not None
        and chain.worker.demodulator.mode == "USB",
        timeout=5000,
    )
    window.close()


def test_close_event_persists_demod_and_step_settings(
    window: MainWindow,
    tmp_config_path: Path,
) -> None:
    window._demod_combo.setCurrentIndex(window._demod_combo.findData("N-FM"))
    window._freq_step_combo.setCurrentIndex(window._freq_step_combo.findData(25_000.0))
    window._gain_step_combo.setCurrentIndex(window._gain_step_combo.findData(0.5))
    window._deemphasis_combo.setCurrentIndex(window._deemphasis_combo.findData(50.0))
    window._nfm_deemphasis_check.setChecked(True)
    window._squelch_check.setChecked(True)
    window._squelch_spin.setValue(-42.5)
    window.close()

    loaded = load_config(tmp_config_path)
    assert loaded.demod_mode == "N-FM"
    assert loaded.freq_step_hz == 25_000.0
    assert loaded.gain_step_db == 0.5
    assert loaded.deemphasis_tau_us == 50.0
    assert loaded.nfm_deemphasis is True
    assert loaded.squelch_enabled is True
    assert loaded.squelch_threshold_db == pytest.approx(-42.5)


def test_deemphasis_controls_update_running_audio_chain(
    window: MainWindow,
    qtbot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sdr_console.demod.fm import WFMDemodulator

    _use_fake_audio_sink(monkeypatch)
    window._audio_check.setChecked(True)
    qtbot.mouseClick(window._start_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window._audio_chain is not None, timeout=5000)

    window._demod_combo.setCurrentIndex(window._demod_combo.findData("W-FM"))
    chain = window._audio_chain
    assert chain is not None
    qtbot.waitUntil(
        lambda: isinstance(chain.worker.demodulator, WFMDemodulator),
        timeout=5000,
    )

    window._deemphasis_combo.setCurrentIndex(window._deemphasis_combo.findData(50.0))
    qtbot.waitUntil(
        lambda: chain.worker.demodulator is not None
        and abs(
            float(getattr(chain.worker.demodulator, "deemphasis_tau_s", 0.0) or 0.0)
            - 50e-6
        )
        < 1e-9,
        timeout=5000,
    )
    window.close()


def test_audio_starts_with_the_stream_and_stops_with_it(
    window: MainWindow,
    qtbot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sinks = _use_fake_audio_sink(monkeypatch)
    window._audio_check.setChecked(True)

    qtbot.mouseClick(window._start_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window._pipeline.is_running, timeout=5000)
    qtbot.waitUntil(lambda: window._audio_chain is not None, timeout=5000)

    chain = window._audio_chain
    assert chain is not None
    assert chain.is_running
    assert sinks[0].sample_rate_hz == pytest.approx(chain.worker.audio_rate_hz())
    assert "audio" in window._streaming_status_text().lower()

    qtbot.mouseClick(window._stop_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not window._pipeline.is_running, timeout=5000)

    assert window._audio_chain is None
    assert not chain.is_running
    # Intent survives the stop, so the next Start plays again.
    assert window._audio_requested


def test_volume_change_while_playing_reaches_the_sink(
    window: MainWindow,
    qtbot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sinks = _use_fake_audio_sink(monkeypatch)
    window._audio_check.setChecked(True)
    qtbot.mouseClick(window._start_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window._audio_chain is not None, timeout=5000)

    window._volume_slider.setValue(20)

    assert sinks[0].volume == pytest.approx(0.2)
    window.close()


def test_bandwidth_change_keeps_the_audio_stream_open(
    window: MainWindow,
    qtbot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sinks = _use_fake_audio_sink(monkeypatch)
    window._audio_check.setChecked(True)
    qtbot.mouseClick(window._start_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window._audio_chain is not None, timeout=5000)

    index = window._bandwidth_combo.findData(200_000.0)
    window._bandwidth_combo.setCurrentIndex(index)

    chain = window._audio_chain
    assert chain is not None
    assert chain.worker.channel.bandwidth_hz == 200_000.0
    # Only one sink was ever created: the stream was not reopened.
    assert len(sinks) == 1
    window.close()


def test_audio_chain_follows_the_listening_frequency(
    window: MainWindow,
    qtbot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_fake_audio_sink(monkeypatch)
    window._audio_check.setChecked(True)
    qtbot.mouseClick(window._start_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window._audio_chain is not None, timeout=5000)

    target_hz = window._device.center_freq_hz + 300_000.0
    window._display.frequency_selected.emit(target_hz)

    chain = window._audio_chain
    assert chain is not None
    assert chain.worker.channel.center_freq_hz == pytest.approx(target_hz)
    window.close()


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


def test_out_of_range_mock_settings_are_clamped_on_startup(
    qtbot, tmp_path: Path
) -> None:
    """Last-session gain/rate outside Mock limits must not abort open."""
    config = AppConfig.default()
    config.device_id = "mock"
    config.gain_db = 73.0
    config.sample_rate_hz = 2_500_000.0

    win = MainWindow(config=config, config_path=tmp_path / "out.json")
    if hasattr(win._device, "realtime"):
        win._device.realtime = False
    qtbot.addWidget(win)

    assert win._config.gain_db == pytest.approx(50.0)
    assert win._config.sample_rate_hz == pytest.approx(2_560_000.0)
    win.close()


def test_out_of_range_pluto_settings_clamp_before_mock_fallback(
    qtbot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pluto gain above 71 must be clamped before create; Mock fallback must also clamp."""
    calls: list[tuple[str, dict]] = []
    real_create = main_window_module.create_device

    def fake_create(device_id: str, **kwargs):
        calls.append((device_id, dict(kwargs)))
        if device_id == "pluto":
            raise ValueError("simulated open failure")
        return real_create(device_id, **kwargs)

    monkeypatch.setattr(main_window_module, "create_device", fake_create)

    config = AppConfig.default()
    config.device_id = "pluto"
    config.gain_db = 73.0
    config.sample_rate_hz = 2_500_000.0

    win = MainWindow(config=config, config_path=tmp_path / "out.json")
    if hasattr(win._device, "realtime"):
        win._device.realtime = False
    qtbot.addWidget(win)

    assert calls[0][0] == "pluto"
    assert calls[0][1]["gain_db"] == pytest.approx(71.0)
    assert calls[0][1]["sample_rate_hz"] == pytest.approx(2_500_000.0)

    assert calls[1][0] == "mock"
    assert calls[1][1]["gain_db"] == pytest.approx(50.0)
    assert calls[1][1]["sample_rate_hz"] == pytest.approx(2_560_000.0)

    assert win._config.device_id == "mock"
    assert win._config.gain_db == pytest.approx(50.0)
    win.close()


def test_detection_toggle_enables_worker_while_streaming(
    window: MainWindow,
    qtbot,
) -> None:
    qtbot.mouseClick(window._start_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window._pipeline.is_running, timeout=5000)

    assert window._detection_worker is not None
    assert not window._detection_worker.enabled

    window._detection_panel._enabled_check.setChecked(True)
    assert window._detection_worker.enabled

    window._detection_panel._enabled_check.setChecked(False)
    assert not window._detection_worker.enabled
    window.close()


def test_center_frequency_change_keeps_confirmed_detection_list(window: MainWindow) -> None:
    from sdr_console.detect.identified import IdentifiedPeak

    assert window._detection_worker is not None
    window._detection_worker.state.replace(
        [
            IdentifiedPeak(
                frequency_hz=101_000_000.0,
                power_db=-20.0,
                capture_gain_db=25.0,
                detection_count=2,
                confirmed_at=1,
                name="Test FM",
            )
        ]
    )
    window._detection_panel.update_peaks(window._detection_worker.state.snapshot())
    assert window._detection_panel._table.rowCount() == 1

    window._center_freq_spin.setValue(120_000_000.0)

    assert len(window._detection_worker.state.snapshot()) == 1
    window._poll_detection_state()
    assert window._detection_panel._table.rowCount() == 1
    assert window._detection_panel._table.item(0, 0).text() == "101.000"


def test_center_frequency_change_resets_candidate_tracking_only(window: MainWindow) -> None:
    from sdr_console.detect.peaks import DetectedPeak

    assert window._detection_worker is not None
    tracker = window._detection_worker.tracker
    signal = DetectedPeak(frequency_hz=101_000_000.0, power_db=-20.0)

    tracker.update([signal], timestamp=0.0, capture_gain_db=20.0)
    tracker.update([signal], timestamp=1.0, capture_gain_db=20.0)
    assert tracker.confirmed_signals() == []

    window._center_freq_spin.setValue(120_000_000.0)

    tracker.update([signal], timestamp=2.0, capture_gain_db=20.0)
    assert tracker.confirmed_signals() == []


def test_detection_threshold_updates_worker(window: MainWindow) -> None:
    worker = window._detection_worker
    assert worker is not None

    window._detection_panel.set_threshold_db(-33.0)
    window._on_detection_threshold_changed(-33.0)

    with worker._settings_lock:
        assert worker._threshold_db == pytest.approx(-33.0)


def test_detection_panel_frequency_cell_tunes_channel(window: MainWindow, qtbot) -> None:
    from sdr_console.detect.identified import IdentifiedPeak

    window._detection_panel.update_peaks(
        [
            IdentifiedPeak(
                frequency_hz=97_000_000.0,
                power_db=-20.0,
                capture_gain_db=25.0,
                detection_count=4,
                confirmed_at=1,
                name="TRT FM",
            )
        ]
    )

    assert window._detection_panel._table.item(0, 0).text() == "97.000"
    assert window._detection_panel._table.item(0, 1).text() == "-20.0"
    assert window._detection_panel._table.item(0, 2).text() == "25.0"
    assert window._detection_panel._table.item(0, 3).text() == "4"

    window._detection_panel._table.cellClicked.emit(0, 0)
    assert window._config.center_freq_hz == pytest.approx(97_000_000.0)
    assert window._config.listen_freq_hz == pytest.approx(97_000_000.0)
    assert window._listen_freq_spin.value() == pytest.approx(97_000_000.0)
    assert window._center_freq_spin.value() == pytest.approx(97_000_000.0)


def test_detection_clear_all_empties_worker_state(window: MainWindow) -> None:
    from sdr_console.detect.identified import IdentifiedPeak

    assert window._detection_worker is not None
    window._detection_worker.state.replace(
        [
            IdentifiedPeak(
                frequency_hz=101_000_000.0,
                power_db=-18.0,
                confirmed_at=1,
            )
        ]
    )

    window._on_detection_clear_all()

    assert window._detection_worker.state.snapshot() == []
    assert window._detection_panel._table.rowCount() == 0


def test_detection_remove_selected_updates_worker_state(window: MainWindow) -> None:
    from sdr_console.detect.peaks import DetectedPeak

    assert window._detection_worker is not None
    tracker = window._detection_worker.tracker
    first = DetectedPeak(frequency_hz=101_000_000.0, power_db=-18.0)
    second = DetectedPeak(frequency_hz=99_000_000.0, power_db=-22.0)

    for timestamp in (0.0, 1.0, 2.0):
        tracker.update([first], timestamp=timestamp, capture_gain_db=20.0)
    for timestamp in (3.0, 4.0, 5.0):
        tracker.update([second], timestamp=timestamp, capture_gain_db=20.0)
    window._detection_worker._publish_confirmed_peaks()
    window._detection_panel.update_peaks(window._detection_worker.state.snapshot())
    window._detection_panel._table.selectRow(0)

    window._on_detection_remove_selected([99_000_000.0])

    remaining = window._detection_worker.state.snapshot()
    assert len(remaining) == 1
    assert remaining[0].frequency_hz == pytest.approx(101_000_000.0)
    assert window._detection_panel._table.rowCount() == 1


def test_main_splitter_grows_content_on_resize(window: MainWindow, qtbot) -> None:
    window.resize(1100, 1200)
    window.show()
    qtbot.waitExposed(window)
    qtbot.waitUntil(lambda: window.height() >= 1150, timeout=2000)

    height_before = window._display.height()

    window.resize(1100, 1500)
    qtbot.waitUntil(lambda: window._display.height() > height_before, timeout=2000)
    assert window._display.height() > height_before


def test_feature_docks_are_visible_by_default(window: MainWindow, qtbot) -> None:
    window.show()
    qtbot.waitExposed(window)

    assert window._detection_panel.isVisible()
    assert window._scan_panel.isVisible()
    assert window._tx_panel.isVisible()
    assert window._detection_panel.title() == "Sinyal Tespiti"
    assert window._scan_panel.title() == "Tarama Modu"
    assert window._tx_panel.title() == "TX / Replay"
    assert window._feature_host.isVisible()
    assert not window._hover_drawer.is_expanded()


def test_control_docks_stack_on_left_and_feature_docks_on_right(
    window: MainWindow,
) -> None:
    assert window._hover_drawer.parentWidget() is not None
    assert window._controls_scroll.parentWidget() is not None
    assert window._receiver_box.parentWidget() is window._controls_column
    assert window._feature_host.parentWidget() is not None


def test_collapsing_control_panels_frees_vertical_space(window: MainWindow, qtbot) -> None:
    window.resize(1100, 800)
    window.show()
    qtbot.waitExposed(window)
    window._sync_main_splitter_to_controls()

    height_before = window._display.height()

    window._receiver_box.set_expanded(False)
    window._audio_box.set_expanded(False)
    window._display_box.set_expanded(False)
    window._on_control_panel_toggled(False)
    qtbot.waitUntil(lambda: window._display.height() >= height_before, timeout=2000)
    assert not window._receiver_box.content_widget().isVisible()


def test_abbreviation_and_status_clarity(window: MainWindow) -> None:
    assert "RF Bandwidth" in window._bandwidth_combo.toolTip() or "RFBW" in window._bandwidth_combo.toolTip()
    assert "AFBW" in window._afbw_combo.toolTip() or "Audio" in window._afbw_combo.toolTip()
    assert "AGC" in window._agc_check.toolTip() or "Automatic" in window._agc_check.toolTip()
    assert "SQL" in window._squelch_check.toolTip() or "Squelch" in window._squelch_check.toolTip()
    assert "VFO" in window._listen_freq_spin.toolTip()
    assert window._status_label.font().bold()
    assert window._status_label.minimumHeight() >= 28

