"""Scrolling waterfall display backed by a fixed-size 2-D buffer."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QRectF, Qt, pyqtSignal

from sdr_console.dsp.axis import band_edges_hz
from sdr_console.dsp.frame import SpectrumFrame
from sdr_console.viz.buffer import append_spectrum_row
from sdr_console.viz.colormap import apply_colormap, apply_db_levels
from sdr_console.viz.interaction import frequency_at_scene_pos
from sdr_console.viz.settings import DisplaySettings


class WaterfallWidget(pg.PlotWidget):
    """Waterfall plot: each new ``SpectrumFrame`` scrolls the image buffer.

    Frequency runs along x (absolute Hz, x-linkable with the spectrum plot) and
    time along y, newest row on top.
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
        self._history_rows = self._settings.history_rows
        self._center_freq_hz = float(center_freq_hz)
        self._sample_rate_hz = float(sample_rate_hz)

        self._history = np.full(
            (self._history_rows, fft_size),
            self._settings.vmin_db,
            dtype=np.float32,
        )

        plot_item = self.getPlotItem()
        plot_item.setLabel("bottom", "Frequency", units="Hz")
        plot_item.setLabel("left", "Time")
        left_axis = plot_item.getAxis("left")
        left_axis.setWidth(self._settings.axis_label_width)
        left_axis.setStyle(showValues=False)
        plot_item.setMouseEnabled(x=True, y=False)
        plot_item.disableAutoRange()
        plot_item.setYRange(0.0, float(self._history_rows), padding=0)

        self._image = pg.ImageItem(self._history, axisOrder="row-major")
        plot_item.addItem(self._image)
        self._apply_settings(self._settings)
        self._rect = QRectF()
        self._update_geometry()

        self.scene().sigMouseClicked.connect(self._on_scene_clicked)

    @property
    def settings(self) -> DisplaySettings:
        return self._settings

    @property
    def history(self) -> np.ndarray:
        return self._history

    @property
    def center_freq_hz(self) -> float:
        return self._center_freq_hz

    @property
    def sample_rate_hz(self) -> float:
        return self._sample_rate_hz

    def set_display_settings(self, settings: DisplaySettings) -> None:
        self._settings = settings
        self.getPlotItem().getAxis("left").setWidth(settings.axis_label_width)
        self._apply_settings(settings)

    def set_tuning(self, center_freq_hz: float, sample_rate_hz: float) -> bool:
        """Re-map the image onto a new frequency span.

        Returns:
            True when the span changed (the view was reset to the full band).
        """
        if (
            center_freq_hz == self._center_freq_hz
            and sample_rate_hz == self._sample_rate_hz
        ):
            return False

        self._center_freq_hz = float(center_freq_hz)
        self._sample_rate_hz = float(sample_rate_hz)
        self._update_geometry()
        return True

    def reset_view(self) -> None:
        """Zoom out to the full observable band."""
        self.setXRange(self._rect.left(), self._rect.right(), padding=0)

    def reset(self) -> None:
        self._history.fill(self._settings.vmin_db)
        self.refresh()

    def append_frame(self, frame: SpectrumFrame) -> None:
        """Update the history buffer without redrawing."""
        if frame.db_values.shape[0] != self._fft_size:
            return
        append_spectrum_row(self._history, frame.db_values)

    def refresh(self) -> None:
        """Push the current history buffer to the ImageItem once."""
        self._image.setImage(self._history, autoLevels=False)
        self._image.setRect(self._rect)

    def _update_geometry(self) -> None:
        low_hz, high_hz = band_edges_hz(self._center_freq_hz, self._sample_rate_hz)
        self._rect = QRectF(
            low_hz,
            0.0,
            high_hz - low_hz,
            float(self._history_rows),
        )
        self._image.setRect(self._rect)
        self.reset_view()

    def _apply_settings(self, settings: DisplaySettings) -> None:
        apply_db_levels(self._image, settings.vmin_db, settings.vmax_db)
        apply_colormap(self._image, settings.colormap)

    def _on_scene_clicked(self, event: object) -> None:
        if event.button() != Qt.MouseButton.LeftButton:  # type: ignore[attr-defined]
            return

        freq_hz = frequency_at_scene_pos(self, event.scenePos())  # type: ignore[attr-defined]
        if freq_hz is not None:
            self.frequency_clicked.emit(freq_hz)
