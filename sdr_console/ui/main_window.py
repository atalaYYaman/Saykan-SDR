"""Main application window."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from sdr_console.config.app_config import AppConfig
from sdr_console.config.storage import save_config
from sdr_console.dsp.channel import ChannelSpec
from sdr_console.hal.discovery import scan_devices
from sdr_console.hal.interface import SDRDeviceInterface
from sdr_console.hal.registry import (
    DEVICE_CHOICES,
    MOCK_DEVICE_ID,
    create_device,
    device_availability,
    is_known_device_id,
)
from sdr_console.pipeline.pipeline import Pipeline
from sdr_console.ui.connect_worker import ConnectWorker
from sdr_console.ui.devices import device_create_kwargs
from sdr_console.viz.sdr_display import SdrDisplayWidget
from sdr_console.viz.settings import DisplaySettings

FFT_SIZE_CHOICES: tuple[int, ...] = (512, 1024, 2048, 4096)


def format_frequency(freq_hz: float) -> str:
    """Human-readable frequency string for status text and labels."""
    magnitude = abs(freq_hz)
    if magnitude >= 1_000_000.0:
        return f"{freq_hz / 1_000_000.0:.6f} MHz"
    if magnitude >= 1_000.0:
        return f"{freq_hz / 1_000.0:.3f} kHz"
    return f"{freq_hz:.0f} Hz"


class MainWindow(QMainWindow):
    """SDR console: device selection, tuning controls, and live display."""

    def __init__(
        self,
        config: AppConfig | None = None,
        config_path: Path | None = None,
    ) -> None:
        super().__init__()
        self._config_path = config_path
        self._config = config or AppConfig.default()
        self._runtime_defaults = self._config.to_defaults()
        self._status_warning = ""
        self._connect_worker: ConnectWorker | None = None
        self._connecting = False
        self._vfo_label: QLabel | None = None

        if not is_known_device_id(self._config.device_id):
            self._status_warning = f"Unknown device '{self._config.device_id}'; using Mock"
            self._config.device_id = MOCK_DEVICE_ID

        self._active_device_id = self._config.device_id

        self.setWindowTitle("SDR Console")
        self.resize(1024, 720)

        self._device = self._create_device(self._active_device_id)
        self._clamp_config_to_capabilities()
        self._apply_config_to_device()

        self._pipeline = self._build_pipeline()
        self._channel = self._channel_from_config()
        self._display = self._create_display()

        self._build_ui()
        self._wire_signals()
        self._select_device_in_combo(self._config.device_id)
        self._sync_controls_from_config()
        self._update_device_availability_ui()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(self._config.display_refresh_ms)
        self._refresh_timer.timeout.connect(self._poll_pipeline_output)

        if self._status_warning:
            self._status_label.setText(self._status_warning)

    def _display_settings_from_config(self) -> DisplaySettings:
        return DisplaySettings(
            vmin_db=self._config.display_vmin_db,
            vmax_db=self._config.display_vmax_db,
            colormap=self._config.display_colormap,
            history_rows=self._config.waterfall_history_rows,
            refresh_ms=self._config.display_refresh_ms,
            spectrum_plot_height=self._config.spectrum_plot_height,
        )

    def _channel_from_config(self) -> ChannelSpec:
        """Build the listening channel from config, clamped to the visible band."""
        spec = ChannelSpec(
            self._config.listen_freq_hz,
            self._config.channel_bandwidth_hz,
        )
        return spec.clamped_to_band(
            self._device.center_freq_hz,
            self._device.sample_rate_hz,
        )

    def _create_display(self) -> SdrDisplayWidget:
        display = SdrDisplayWidget(
            fft_size=self._config.fft_size,
            settings=self._display_settings_from_config(),
            center_freq_hz=self._device.center_freq_hz,
            sample_rate_hz=self._device.sample_rate_hz,
            channel=self._channel,
        )
        display.frequency_selected.connect(self._on_frequency_selected)
        display.channel_moved.connect(self._on_frequency_selected)
        return display

    def _build_pipeline(self) -> Pipeline:
        return Pipeline(
            device=self._device,
            fft_size=self._config.fft_size,
            output_queue_maxsize=self._runtime_defaults.queue_maxsize,
            raw_queue_maxsize=self._runtime_defaults.raw_queue_maxsize,
            on_error=self._on_pipeline_error,
        )

    def _create_device(self, device_id: str) -> SDRDeviceInterface:
        kwargs = device_create_kwargs(device_id, self._config, self._runtime_defaults)
        try:
            return create_device(device_id, **kwargs)
        except ValueError:
            self._status_warning = f"Unsupported device '{device_id}'; using Mock"
            self._active_device_id = MOCK_DEVICE_ID
            self._config.device_id = MOCK_DEVICE_ID
            kwargs = device_create_kwargs(
                MOCK_DEVICE_ID, self._config, self._runtime_defaults
            )
            return create_device(MOCK_DEVICE_ID, **kwargs)

    def _clamp_config_to_capabilities(self) -> None:
        caps = self._device.capabilities
        try:
            caps.validate_freq_hz(self._config.center_freq_hz)
        except ValueError:
            self._config.center_freq_hz = (
                caps.min_freq_hz + caps.max_freq_hz
            ) / 2.0

        try:
            caps.validate_gain_db(self._config.gain_db)
        except ValueError:
            self._config.gain_db = (caps.min_gain_db + caps.max_gain_db) / 2.0

        try:
            caps.validate_sample_rate_hz(self._config.sample_rate_hz)
        except ValueError:
            if caps.supported_sample_rates_hz:
                self._config.sample_rate_hz = caps.supported_sample_rates_hz[0]
            elif caps.min_sample_rate_hz is not None:
                self._config.sample_rate_hz = caps.min_sample_rate_hz

        try:
            caps.validate_gain_mode(self._config.gain_mode)
        except ValueError:
            self._config.gain_mode = caps.gain_modes[0] if caps.gain_modes else "manual"

    def _apply_config_to_device(self) -> None:
        self._device.set_center_freq(self._config.center_freq_hz)
        self._device.set_gain(self._config.gain_db)
        self._device.set_sample_rate(self._config.sample_rate_hz)
        try:
            self._device.set_gain_mode(self._config.gain_mode)
        except ValueError:
            self._config.gain_mode = self._device.gain_mode

    def _select_device_in_combo(self, device_id: str) -> None:
        index = self._device_combo.findData(device_id)
        if index >= 0:
            self._device_combo.blockSignals(True)
            self._device_combo.setCurrentIndex(index)
            self._device_combo.blockSignals(False)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        transport_row = QHBoxLayout()
        self._device_combo = QComboBox()
        for device_id, label in DEVICE_CHOICES:
            self._device_combo.addItem(label, device_id)

        self._uri_edit = QLineEdit()
        self._uri_edit.setPlaceholderText("auto / ip:192.168.2.1 / usb:")
        self._uri_edit.setMinimumWidth(180)
        self._uri_edit.setText(self._config.device_uri)

        self._scan_button = QPushButton("Scan")
        self._start_button = QPushButton("Start")
        self._stop_button = QPushButton("Stop")
        self._stop_button.setEnabled(False)

        transport_row.addWidget(QLabel("Device:"))
        transport_row.addWidget(self._device_combo)
        transport_row.addWidget(QLabel("URI:"))
        transport_row.addWidget(self._uri_edit)
        transport_row.addWidget(self._scan_button)
        transport_row.addWidget(self._start_button)
        transport_row.addWidget(self._stop_button)
        transport_row.addStretch()
        root.addLayout(transport_row)

        tuning_box = QGroupBox("Receiver")
        tuning_form = QFormLayout(tuning_box)
        caps = self._device.capabilities

        self._center_freq_spin = QDoubleSpinBox()
        self._center_freq_spin.setSuffix(" Hz")
        self._center_freq_spin.setDecimals(0)
        self._center_freq_spin.setRange(caps.min_freq_hz, caps.max_freq_hz)
        self._center_freq_spin.setSingleStep(1_000_000.0)

        self._gain_spin = QDoubleSpinBox()
        self._gain_spin.setSuffix(" dB")
        self._gain_spin.setDecimals(1)
        self._gain_spin.setRange(caps.min_gain_db, caps.max_gain_db)
        self._gain_spin.setSingleStep(1.0)

        self._gain_mode_combo = QComboBox()
        for mode in caps.gain_modes:
            self._gain_mode_combo.addItem(mode, mode)

        self._sample_rate_combo = QComboBox()
        self._configure_sample_rate_combo(caps)

        self._fft_size_combo = QComboBox()
        for size in FFT_SIZE_CHOICES:
            self._fft_size_combo.addItem(str(size), size)

        self._vfo_label = QLabel()
        self._vfo_label.setToolTip(
            "Click the spectrum or waterfall, or drag the highlighted box, "
            "to move the listening frequency"
        )

        tuning_form.addRow("Center frequency", self._center_freq_spin)
        tuning_form.addRow("Gain", self._gain_spin)
        tuning_form.addRow("Gain mode", self._gain_mode_combo)
        tuning_form.addRow("Sample rate", self._sample_rate_combo)
        tuning_form.addRow("FFT size", self._fft_size_combo)
        tuning_form.addRow("Listen (VFO)", self._vfo_label)
        root.addWidget(tuning_box)

        display_box = QGroupBox("Display")
        display_form = QFormLayout(display_box)
        self._vmin_spin = QDoubleSpinBox()
        self._vmin_spin.setSuffix(" dB")
        self._vmin_spin.setDecimals(1)
        self._vmin_spin.setRange(-200.0, 50.0)
        self._vmax_spin = QDoubleSpinBox()
        self._vmax_spin.setSuffix(" dB")
        self._vmax_spin.setDecimals(1)
        self._vmax_spin.setRange(-200.0, 50.0)
        display_form.addRow("dB min (vmin)", self._vmin_spin)
        display_form.addRow("dB max (vmax)", self._vmax_spin)
        root.addWidget(display_box)

        root.addWidget(self._display, stretch=1)

        self._status_label = QLabel("Idle")
        root.addWidget(self._status_label)

        self._update_gain_mode_visibility()

    def _configure_sample_rate_combo(self, caps) -> None:
        """Populate sample-rate combo; editable when continuous rates are allowed."""
        self._sample_rate_combo.blockSignals(True)
        self._sample_rate_combo.clear()
        for rate in caps.supported_sample_rates_hz:
            self._sample_rate_combo.addItem(f"{rate:g} sps", rate)
        continuous = caps.has_continuous_sample_rates
        self._sample_rate_combo.setEditable(continuous)
        if continuous and self._sample_rate_combo.lineEdit() is not None:
            self._sample_rate_combo.lineEdit().setPlaceholderText("Hz (continuous)")
        self._sample_rate_combo.blockSignals(False)

    def _wire_signals(self) -> None:
        self._start_button.clicked.connect(self._on_start)
        self._stop_button.clicked.connect(self._on_stop)
        self._scan_button.clicked.connect(self._on_scan)
        self._device_combo.currentIndexChanged.connect(self._on_device_changed)
        self._uri_edit.editingFinished.connect(self._on_uri_changed)
        self._center_freq_spin.valueChanged.connect(self._on_center_freq_changed)
        self._gain_spin.valueChanged.connect(self._on_gain_changed)
        self._gain_mode_combo.currentIndexChanged.connect(self._on_gain_mode_changed)
        self._sample_rate_combo.currentIndexChanged.connect(self._on_sample_rate_changed)
        self._sample_rate_combo.editTextChanged.connect(self._on_sample_rate_edited)
        self._fft_size_combo.currentIndexChanged.connect(self._on_fft_size_changed)
        self._vmin_spin.valueChanged.connect(self._on_display_levels_changed)
        self._vmax_spin.valueChanged.connect(self._on_display_levels_changed)

    def _sync_controls_from_config(self) -> None:
        widgets = (
            self._center_freq_spin,
            self._gain_spin,
            self._vmin_spin,
            self._vmax_spin,
            self._sample_rate_combo,
            self._fft_size_combo,
            self._gain_mode_combo,
            self._uri_edit,
        )
        for widget in widgets:
            widget.blockSignals(True)

        self._center_freq_spin.setValue(self._device.center_freq_hz)
        self._gain_spin.setValue(self._device.gain_db)
        self._uri_edit.setText(self._config.device_uri)

        mode_index = self._gain_mode_combo.findData(self._device.gain_mode)
        if mode_index < 0:
            mode_index = self._gain_mode_combo.findData(self._config.gain_mode)
        if mode_index >= 0:
            self._gain_mode_combo.setCurrentIndex(mode_index)

        rate = self._device.sample_rate_hz
        rate_index = self._sample_rate_combo.findData(rate)
        if rate_index >= 0:
            self._sample_rate_combo.setCurrentIndex(rate_index)
        elif self._sample_rate_combo.isEditable():
            self._sample_rate_combo.setEditText(f"{rate:g}")

        fft_index = self._fft_size_combo.findData(self._config.fft_size)
        if fft_index >= 0:
            self._fft_size_combo.setCurrentIndex(fft_index)

        self._vmin_spin.setValue(self._config.display_vmin_db)
        self._vmax_spin.setValue(self._config.display_vmax_db)

        for widget in widgets:
            widget.blockSignals(False)

        self._update_gain_spin_enabled()
        self._update_vfo_label()

    def _update_vfo_label(self) -> None:
        if self._vfo_label is None:
            return
        self._vfo_label.setText(
            f"{format_frequency(self._channel.center_freq_hz)}  "
            f"(BW {format_frequency(self._channel.bandwidth_hz)})"
        )

    def _set_channel(self, channel: ChannelSpec) -> None:
        """Store the listening channel and mirror it to config and the overlay."""
        clamped = channel.clamped_to_band(
            self._device.center_freq_hz,
            self._device.sample_rate_hz,
        )
        self._channel = clamped
        self._config.listen_freq_hz = clamped.center_freq_hz
        self._config.channel_bandwidth_hz = clamped.bandwidth_hz
        self._display.set_channel(clamped)
        self._update_vfo_label()

    def _on_frequency_selected(self, freq_hz: float) -> None:
        """User picked a frequency on the plots; UI state only (no retune)."""
        self._set_channel(self._channel.with_center(freq_hz))

    def _sync_display_tuning(self) -> None:
        """Push current device tuning to the plots and re-clamp the channel."""
        self._display.set_tuning(
            self._device.center_freq_hz,
            self._device.sample_rate_hz,
        )
        self._set_channel(self._channel)

    def _poll_pipeline_output(self) -> None:
        self._display.poll_queue(self._pipeline.output_queue)
        if self._pipeline.is_running:
            dropped = self._pipeline.dropped_blocks
            label = self._streaming_status_text()
            if dropped:
                label = f"{label} — dropped {dropped}"
            self._status_label.setText(label)

    def _streaming_status_text(self) -> str:
        name = self._device_combo.currentText() or self._active_device_id
        return f"Streaming ({name})"

    def _on_start(self) -> None:
        if self._pipeline.is_running or self._connecting:
            return

        available, reason = device_availability(self._active_device_id)
        if not available and self._active_device_id != MOCK_DEVICE_ID:
            self._status_label.setText(reason or "Device unavailable")
            return

        self._capture_config_from_ui()
        self._apply_tuning_to_device()
        self._pipeline.drain_output()
        self._display.reset()

        self._connecting = True
        self._start_button.setEnabled(False)
        self._stop_button.setEnabled(False)
        self._device_combo.setEnabled(False)
        self._fft_size_combo.setEnabled(False)
        self._scan_button.setEnabled(False)
        self._status_label.setText("Connecting…")

        worker = ConnectWorker(self._device, parent=self)
        self._connect_worker = worker
        worker.connected.connect(self._on_connect_succeeded)
        worker.failed.connect(self._on_connect_failed)
        worker.finished.connect(self._on_connect_finished)
        worker.start()

    def _on_connect_succeeded(self) -> None:
        self._clamp_config_to_capabilities()
        self._rebuild_tuning_ranges()
        self._sync_controls_from_config()
        self._sync_display_tuning()
        self._pipeline.start()
        self._refresh_timer.start()
        self._stop_button.setEnabled(True)
        self._status_label.setText(self._streaming_status_text())

    def _on_connect_failed(self, message: str) -> None:
        self._status_label.setText(f"Connect failed: {message}")
        self._start_button.setEnabled(True)
        self._device_combo.setEnabled(True)
        self._fft_size_combo.setEnabled(True)
        self._scan_button.setEnabled(True)
        try:
            self._device.disconnect()
        except Exception:
            pass

    def _on_connect_finished(self) -> None:
        self._connecting = False
        self._connect_worker = None

    def _on_stop(self) -> None:
        self._refresh_timer.stop()
        self._pipeline.stop()
        try:
            self._device.disconnect()
        except Exception:
            pass

        self._start_button.setEnabled(True)
        self._stop_button.setEnabled(False)
        self._device_combo.setEnabled(True)
        self._fft_size_combo.setEnabled(True)
        self._scan_button.setEnabled(True)
        self._status_label.setText("Idle")

    def _on_pipeline_error(self, message: str) -> None:
        # Called from acquisition thread — marshal to GUI thread.
        QTimer.singleShot(0, lambda: self._handle_pipeline_error(message))

    def _handle_pipeline_error(self, message: str) -> None:
        if self._pipeline.is_running or self._device.is_connected:
            self._on_stop()
        self._status_label.setText(f"Stream error: {message}")

    def _on_scan(self) -> None:
        if self._pipeline.is_running or self._connecting:
            return
        found = scan_devices()
        if not found:
            self._status_label.setText("Scan: no devices found")
            return

        # Prefer first discovered URI for the matching device type.
        first = found[0]
        if first.device_id != self._active_device_id:
            index = self._device_combo.findData(first.device_id)
            if index >= 0:
                self._device_combo.setCurrentIndex(index)

        self._uri_edit.setText(first.uri)
        self._config.device_uri = first.uri
        labels = ", ".join(d.label for d in found)
        self._status_label.setText(f"Scan found: {labels}")

        # Recreate device so URI is applied.
        self._reload_selected_device(force=True)

    def _on_uri_changed(self) -> None:
        self._config.device_uri = self._uri_edit.text().strip()
        if self._pipeline.is_running or self._connecting:
            return
        # Recreate device with new URI when idle.
        self._reload_selected_device(force=True)

    def _on_device_changed(self, *_args: object) -> None:
        """Handle device combo changes (Qt may pass the new index)."""
        self._reload_selected_device(force=False)

    def _reload_selected_device(self, *, force: bool = False) -> None:
        if self._pipeline.is_running or self._connecting:
            return

        device_id = self._device_combo.currentData()
        if device_id is None:
            return
        if (
            not force
            and device_id == self._active_device_id
            and self._config.device_uri == self._uri_edit.text().strip()
        ):
            return

        self._capture_config_from_ui()
        self._active_device_id = device_id
        self._config.device_id = device_id
        self._device = self._create_device(device_id)
        self._clamp_config_to_capabilities()
        self._apply_config_to_device()
        self._rebuild_tuning_ranges()
        self._pipeline = self._build_pipeline()
        self._sync_controls_from_config()
        self._sync_display_tuning()
        self._update_device_availability_ui()

        available, reason = device_availability(device_id)
        if available:
            self._status_label.setText(f"Selected {self._device_combo.currentText()}")
        else:
            self._status_label.setText(
                f"Selected {self._device_combo.currentText()} — {reason}"
            )

    def _update_device_availability_ui(self) -> None:
        for index in range(self._device_combo.count()):
            device_id = self._device_combo.itemData(index)
            available, reason = device_availability(str(device_id))
            # Keep mock always enabled; others use availability.
            enabled = available or device_id == MOCK_DEVICE_ID
            model = self._device_combo.model()
            item = model.item(index) if hasattr(model, "item") else None
            if item is not None:
                flags = item.flags()
                if enabled:
                    item.setFlags(flags | Qt.ItemFlag.ItemIsEnabled)
                else:
                    item.setFlags(flags & ~Qt.ItemFlag.ItemIsEnabled)
                if reason and not available:
                    item.setToolTip(reason)
                else:
                    item.setToolTip("")

    def _rebuild_tuning_ranges(self) -> None:
        caps = self._device.capabilities
        self._center_freq_spin.setRange(caps.min_freq_hz, caps.max_freq_hz)
        self._gain_spin.setRange(caps.min_gain_db, caps.max_gain_db)
        self._configure_sample_rate_combo(caps)

        self._gain_mode_combo.blockSignals(True)
        self._gain_mode_combo.clear()
        for mode in caps.gain_modes:
            self._gain_mode_combo.addItem(mode, mode)
        self._gain_mode_combo.blockSignals(False)
        self._update_gain_mode_visibility()

    def _update_gain_mode_visibility(self) -> None:
        caps = self._device.capabilities
        multi = len(caps.gain_modes) > 1
        self._gain_mode_combo.setVisible(multi)
        # Hide the form label by finding the buddy row — keep simple: always
        # leave the widget; when single-mode it still shows "manual".
        self._update_gain_spin_enabled()

    def _update_gain_spin_enabled(self) -> None:
        mode = self._gain_mode_combo.currentData() or self._config.gain_mode
        self._gain_spin.setEnabled(mode == "manual" or mode is None)

    def _current_sample_rate(self) -> float | None:
        rate = self._sample_rate_combo.currentData()
        if rate is not None:
            return float(rate)
        if self._sample_rate_combo.isEditable():
            text = self._sample_rate_combo.currentText().strip().split()[0]
            try:
                return float(text)
            except ValueError:
                return None
        return None

    def _apply_tuning_to_device(self) -> None:
        self._device.set_center_freq(self._center_freq_spin.value())
        self._device.set_gain(self._gain_spin.value())
        rate = self._current_sample_rate()
        if rate is not None:
            self._device.set_sample_rate(float(rate))
        mode = self._gain_mode_combo.currentData()
        if mode is not None:
            try:
                self._device.set_gain_mode(str(mode))
            except ValueError as exc:
                self._status_label.setText(str(exc))

    def _on_center_freq_changed(self, value: float) -> None:
        self._apply_device_setter(
            lambda: self._device.set_center_freq(value),
            self._center_freq_spin,
            self._device.center_freq_hz,
        )
        self._sync_display_tuning()

    def _on_gain_changed(self, value: float) -> None:
        self._apply_device_setter(
            lambda: self._device.set_gain(value),
            self._gain_spin,
            self._device.gain_db,
        )

    def _on_gain_mode_changed(self) -> None:
        mode = self._gain_mode_combo.currentData()
        if mode is None:
            return
        try:
            self._device.set_gain_mode(str(mode))
            self._config.gain_mode = str(mode)
        except ValueError as exc:
            self._status_label.setText(str(exc))
            return
        self._update_gain_spin_enabled()
        self._set_idle_or_streaming_status()

    def _on_sample_rate_changed(self) -> None:
        rate = self._current_sample_rate()
        if rate is None:
            return
        try:
            self._device.set_sample_rate(float(rate))
            self._config.sample_rate_hz = float(rate)
        except ValueError as exc:
            self._status_label.setText(str(exc))
            return
        self._sync_display_tuning()
        self._set_idle_or_streaming_status()

    def _on_sample_rate_edited(self, text: str) -> None:
        if not self._sample_rate_combo.isEditable():
            return
        cleaned = text.strip().split()[0] if text.strip() else ""
        if not cleaned:
            return
        try:
            rate = float(cleaned)
        except ValueError:
            return
        try:
            self._device.set_sample_rate(rate)
            self._config.sample_rate_hz = rate
        except ValueError:
            return
        self._sync_display_tuning()

    def _on_fft_size_changed(self) -> None:
        if self._pipeline.is_running or self._connecting:
            return
        size = self._fft_size_combo.currentData()
        if size is None or size == self._config.fft_size:
            return

        self._config.fft_size = int(size)
        was_connected = self._device.is_connected
        self._pipeline.stop()
        self._pipeline = self._build_pipeline()

        layout = self.centralWidget().layout()
        assert layout is not None
        layout.removeWidget(self._display)
        self._display.deleteLater()
        self._display = self._create_display()
        layout.insertWidget(layout.count() - 1, self._display, stretch=1)

        if was_connected:
            self._device.connect()

        self._status_label.setText(f"FFT size set to {self._config.fft_size}")

    def _on_display_levels_changed(self) -> None:
        vmin = self._vmin_spin.value()
        vmax = self._vmax_spin.value()
        if vmin >= vmax:
            self._status_label.setText("dB min must be less than dB max")
            return

        self._config.display_vmin_db = vmin
        self._config.display_vmax_db = vmax
        self._display.set_display_settings(self._display_settings_from_config())
        self._set_idle_or_streaming_status()

    def _apply_device_setter(
        self,
        setter: Callable[[], None],
        spin: QDoubleSpinBox,
        valid_value: float,
    ) -> None:
        try:
            setter()
        except ValueError as exc:
            spin.blockSignals(True)
            spin.setValue(valid_value)
            spin.blockSignals(False)
            self._status_label.setText(str(exc))
            return

        self._set_idle_or_streaming_status()

    def _set_idle_or_streaming_status(self) -> None:
        if self._connecting:
            self._status_label.setText("Connecting…")
        elif self._pipeline.is_running:
            self._status_label.setText(self._streaming_status_text())
        else:
            self._status_label.setText("Idle")

    def _capture_config_from_ui(self) -> None:
        self._config.device_id = self._device_combo.currentData()
        self._config.device_uri = self._uri_edit.text().strip()
        self._config.center_freq_hz = self._center_freq_spin.value()
        self._config.gain_db = self._gain_spin.value()
        mode = self._gain_mode_combo.currentData()
        if mode is not None:
            self._config.gain_mode = str(mode)
        rate = self._current_sample_rate()
        if rate is not None:
            self._config.sample_rate_hz = float(rate)
        fft_size = self._fft_size_combo.currentData()
        if fft_size is not None:
            self._config.fft_size = int(fft_size)
        self._config.display_vmin_db = self._vmin_spin.value()
        self._config.display_vmax_db = self._vmax_spin.value()
        self._config.listen_freq_hz = self._channel.center_freq_hz
        self._config.channel_bandwidth_hz = self._channel.bandwidth_hz

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 — Qt API
        if self._connect_worker is not None and self._connect_worker.isRunning():
            self._connect_worker.wait(2000)
        self._on_stop()
        self._capture_config_from_ui()
        save_config(self._config, self._config_path)
        super().closeEvent(event)
