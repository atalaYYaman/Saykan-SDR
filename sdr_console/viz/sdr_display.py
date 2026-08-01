"""Combined spectrum + waterfall display sharing one frequency axis."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from sdr_console.dsp.channel import ChannelSpec
from sdr_console.dsp.frame import SpectrumFrame
from sdr_console.pipeline.sample_queue import SampleQueue
from sdr_console.viz.band_overlay import BandOverlay
from sdr_console.viz.settings import DisplaySettings
from sdr_console.viz.spectrum_widget import SpectrumWidget
from sdr_console.viz.waterfall_widget import WaterfallWidget

DEFAULT_CHANNEL_BANDWIDTH_HZ = 200_000.0


class SdrDisplayWidget(QWidget):
    """Spectrum + waterfall plots updated by the UI layer from a pipeline queue.

    Both plots share the x axis (absolute Hz) so zoom and pan stay in lockstep,
    and both carry the channel overlay box. User interaction is reported as
    signals; this widget never touches the device or the pipeline itself.
    """

    frequency_selected = pyqtSignal(float)
    channel_moved = pyqtSignal(float)

    def __init__(
        self,
        fft_size: int,
        settings: DisplaySettings | None = None,
        center_freq_hz: float = 0.0,
        sample_rate_hz: float = 1.0,
        channel: ChannelSpec | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._fft_size = fft_size
        self._settings = settings or DisplaySettings()
        self._syncing_overlay = False

        self._spectrum = SpectrumWidget(
            fft_size,
            settings=self._settings,
            center_freq_hz=center_freq_hz,
            sample_rate_hz=sample_rate_hz,
        )
        self._waterfall = WaterfallWidget(
            fft_size,
            settings=self._settings,
            center_freq_hz=center_freq_hz,
            sample_rate_hz=sample_rate_hz,
        )
        self._waterfall.setXLink(self._spectrum)

        self._channel = channel or ChannelSpec(
            center_freq_hz, DEFAULT_CHANNEL_BANDWIDTH_HZ
        )
        self._overlays = (
            BandOverlay(self._spectrum.getPlotItem(), self._settings),
            BandOverlay(self._waterfall.getPlotItem(), self._settings),
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._spectrum, stretch=0)
        self._spectrum.setFixedHeight(self._settings.spectrum_plot_height)
        layout.addWidget(self._waterfall, stretch=1)

        self._spectrum.frequency_clicked.connect(self.frequency_selected)
        self._waterfall.frequency_clicked.connect(self.frequency_selected)
        for overlay in self._overlays:
            overlay.region.sigRegionChanged.connect(self._on_overlay_dragged)

        self.set_channel(self._channel)

    @property
    def settings(self) -> DisplaySettings:
        return self._settings

    @property
    def spectrum(self) -> SpectrumWidget:
        return self._spectrum

    @property
    def waterfall(self) -> WaterfallWidget:
        return self._waterfall

    @property
    def channel(self) -> ChannelSpec:
        return self._channel

    def set_display_settings(self, settings: DisplaySettings) -> None:
        self._settings = settings
        self._spectrum.setFixedHeight(settings.spectrum_plot_height)
        self._spectrum.set_display_settings(settings)
        self._waterfall.set_display_settings(settings)
        for overlay in self._overlays:
            overlay.set_display_settings(settings)

    def set_channel(self, channel: ChannelSpec) -> None:
        """Move the overlay box onto ``channel`` without re-emitting signals."""
        self._channel = channel
        self._syncing_overlay = True
        try:
            for overlay in self._overlays:
                overlay.set_channel(channel)
        finally:
            self._syncing_overlay = False

    def set_tuning(self, center_freq_hz: float, sample_rate_hz: float) -> None:
        """Update both frequency axes for new receiver tuning."""
        self._spectrum.set_tuning(center_freq_hz, sample_rate_hz)
        self._waterfall.set_tuning(center_freq_hz, sample_rate_hz)

    def reset(self) -> None:
        self._spectrum.reset()
        self._waterfall.reset()

    def poll_queue(self, data_queue: SampleQueue[SpectrumFrame]) -> None:
        """Drain available frames and refresh plots once per call."""
        latest: SpectrumFrame | None = None
        updated = False

        while True:
            frame = data_queue.try_get()
            if frame is None:
                break

            if frame.db_values.shape[0] != self._fft_size:
                continue

            self._waterfall.append_frame(frame)
            latest = frame
            updated = True

        if updated:
            self._waterfall.refresh()
        if latest is not None:
            self.set_tuning(latest.center_freq, latest.sample_rate)
            self._spectrum.update_frame(latest)

    def _on_overlay_dragged(self, region: object) -> None:
        if self._syncing_overlay:
            return

        low_hz, high_hz = region.getRegion()  # type: ignore[attr-defined]
        self.channel_moved.emit((low_hz + high_hz) / 2.0)
