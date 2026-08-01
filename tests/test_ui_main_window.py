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


def test_demod_mode_switch_sets_default_bandwidth(window: MainWindow) -> None:
    index = window._demod_combo.findData("CW")
    window._demod_combo.setCurrentIndex(index)

    assert window._config.demod_mode == "CW"
    assert window._channel.bandwidth_hz == 500.0
    assert "CW" in window._vfo_label.text()


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
    window.close()

    loaded = load_config(tmp_config_path)
    assert loaded.demod_mode == "N-FM"
    assert loaded.freq_step_hz == 25_000.0
    assert loaded.gain_step_db == 0.5


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
