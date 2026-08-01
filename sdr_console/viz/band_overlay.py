"""Translucent overlay marking the selected listening channel."""

from __future__ import annotations

import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from sdr_console.dsp.channel import ChannelSpec
from sdr_console.viz.settings import DisplaySettings


class BandOverlay:
    """Channel bandwidth box plus center marker drawn on a single plot.

    Draw-only: the box position is pushed in via :meth:`set_channel`. When
    ``movable`` is true the user can drag the whole box sideways; edge dragging
    is disabled because bandwidth is owned by the UI controls.
    """

    def __init__(
        self,
        plot_item: pg.PlotItem,
        settings: DisplaySettings | None = None,
        movable: bool = True,
    ) -> None:
        self._settings = settings or DisplaySettings()

        self._region = pg.LinearRegionItem(values=(0.0, 0.0), movable=movable)
        self._region.setZValue(20)
        for line in self._region.lines:
            line.setMovable(False)

        self._center_line = pg.InfiniteLine(angle=90, movable=False)
        self._center_line.setZValue(21)

        self._apply_settings(self._settings)

        plot_item.addItem(self._region, ignoreBounds=True)
        plot_item.addItem(self._center_line, ignoreBounds=True)

    @property
    def region(self) -> pg.LinearRegionItem:
        """Underlying region item; connect to its signals for drag events."""
        return self._region

    def set_channel(self, channel: ChannelSpec) -> None:
        """Move the box and center marker onto ``channel``."""
        self._region.setRegion((channel.low_hz, channel.high_hz))
        self._center_line.setPos(channel.center_freq_hz)

    def channel_from_region(self, bandwidth_hz: float) -> ChannelSpec:
        """Build a spec from the current box position, keeping ``bandwidth_hz``."""
        low_hz, high_hz = self._region.getRegion()
        return ChannelSpec((low_hz + high_hz) / 2.0, bandwidth_hz)

    def set_display_settings(self, settings: DisplaySettings) -> None:
        self._settings = settings
        self._apply_settings(settings)

    def _apply_settings(self, settings: DisplaySettings) -> None:
        fill = QColor(settings.channel_fill_color)
        fill.setAlpha(settings.channel_fill_alpha)
        self._region.setBrush(pg.mkBrush(fill))

        edge_pen = pg.mkPen(QColor(settings.channel_fill_color), width=1)
        for line in self._region.lines:
            line.setPen(edge_pen)

        self._center_line.setPen(
            pg.mkPen(
                QColor(settings.channel_line_color),
                width=1,
                style=Qt.PenStyle.DashLine,
            )
        )
