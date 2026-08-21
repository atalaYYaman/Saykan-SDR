"""Single-row live spectrum plot on an absolute frequency axis."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QSizePolicy

from sdr_console.dsp.axis import band_edges_hz, frequency_axis_hz
from sdr_console.dsp.frame import SpectrumFrame
from sdr_console.viz.interaction import frequency_at_scene_pos
from sdr_console.viz.plot_theme import apply_plot_chrome
from sdr_console.viz.settings import DisplaySettings


def _prepare_fill_plot(plot: pg.PlotWidget) -> None:
    """Stretch the ViewBox to the widget so the curve is not letterboxed."""
    plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    plot.setMinimumWidth(0)
    if hasattr(plot, "setAspectLocked"):
        plot.setAspectLocked(False)
    plot_item = plot.getPlotItem()
    plot_item.setContentsMargins(0, 0, 0, 0)
    plot_item.hideButtons()
    layout = plot_item.layout
    if layout is not None:
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
    view_box = plot_item.getViewBox()
    view_box.setAspectLocked(False)
    view_box.setDefaultPadding(0.0)
    view_box.enableAutoRange(x=False, y=False)


class SpectrumWidget(pg.PlotWidget):
    """Instantaneous power spectrum for the latest ``SpectrumFrame``.

    The x axis carries absolute RF frequency in Hz so it can be x-linked with
    the waterfall. Tick labels are hidden here; the shared frequency scale is
    drawn once, under the waterfall.
    """

    frequency_clicked = pyqtSignal(float)

    def __init__(
        self,
        fft_size: int,
        settings: DisplaySettings | None = None,
        center_freq_hz: float = 0.0,
        sample_rate_hz: float = 1.0,
        parent: pg.PlotWidget | None = None,
    ) -> None:
        super().__init__(parent=parent)
        self._settings = settings or DisplaySettings()
        self._fft_size = fft_size
        self._center_freq_hz = float(center_freq_hz)
        self._sample_rate_hz = float(sample_rate_hz)
        self._x = frequency_axis_hz(self._center_freq_hz, self._sample_rate_hz, fft_size)

        _prepare_fill_plot(self)
        apply_plot_chrome(self, self._settings)
        plot_item = self.getPlotItem()
        plot_item.setLabel("left", "Power (dBFS)")
        plot_item.getAxis("left").setWidth(self._settings.axis_label_width)
        plot_item.getAxis("bottom").setStyle(showValues=False)
        plot_item.setMouseEnabled(x=True, y=False)
        plot_item.disableAutoRange()
        plot_item.setYRange(self._settings.vmin_db, self._settings.vmax_db, padding=0)

        self._curve = plot_item.plot(
            self._x,
            np.full(fft_size, self._settings.vmin_db, dtype=np.float64),
            pen=pg.mkPen(color=self._settings.spectrum_pen_color, width=1),
        )
        self.reset_view()

        self.scene().sigMouseClicked.connect(self._on_scene_clicked)

    @property
    def settings(self) -> DisplaySettings:
        return self._settings

    @property
    def center_freq_hz(self) -> float:
        return self._center_freq_hz

    @property
    def sample_rate_hz(self) -> float:
        return self._sample_rate_hz

    def set_display_settings(self, settings: DisplaySettings) -> None:
        self._settings = settings
        apply_plot_chrome(self, settings)
        self.getPlotItem().getAxis("left").setWidth(settings.axis_label_width)
        self.setYRange(settings.vmin_db, settings.vmax_db, padding=0)
        self._curve.setPen(pg.mkPen(color=settings.spectrum_pen_color, width=1))

    def set_tuning(self, center_freq_hz: float, sample_rate_hz: float) -> bool:
        """Rebuild the frequency axis for new receiver tuning.

        Returns:
            True when the axis changed (the view was reset to the full band).
        """
        if (
            center_freq_hz == self._center_freq_hz
            and sample_rate_hz == self._sample_rate_hz
        ):
            return False

        self._center_freq_hz = float(center_freq_hz)
        self._sample_rate_hz = float(sample_rate_hz)
        self._x = frequency_axis_hz(
            self._center_freq_hz, self._sample_rate_hz, self._fft_size
        )
        self._curve.setData(self._x, self._curve.yData)
        self.reset_view()
        return True

    def reset_view(self) -> None:
        """Zoom out to the full observable band."""
        low_hz, high_hz = band_edges_hz(self._center_freq_hz, self._sample_rate_hz)
        self.setXRange(low_hz, high_hz, padding=0)

    def reset(self) -> None:
        self._curve.setData(
            self._x,
            np.full(self._fft_size, self._settings.vmin_db, dtype=np.float64),
        )

    def update_frame(self, frame: SpectrumFrame) -> None:
        if frame.db_values.shape[0] != self._fft_size:
            return

        self._curve.setData(self._x, frame.db_values)

    def _on_scene_clicked(self, event: object) -> None:
        if event.button() != Qt.MouseButton.LeftButton:  # type: ignore[attr-defined]
            return

        freq_hz = frequency_at_scene_pos(self, event.scenePos())  # type: ignore[attr-defined]
        if freq_hz is not None:
            self.frequency_clicked.emit(freq_hz)
