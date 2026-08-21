"""Plot chrome colors aligned with design-system/MASTER.md §6.1.

Kept in viz (not ui.theme) so the visualization layer does not depend on UI.
"""

from __future__ import annotations

import pyqtgraph as pg
from PyQt6.QtGui import QFont

from sdr_console.viz.settings import DisplaySettings


def apply_plot_chrome(
    plot: pg.PlotWidget,
    settings: DisplaySettings,
    *,
    grid: bool = True,
) -> None:
    """Background, axis text, optional grid — no DSP, draw-only."""
    plot.setBackground(settings.plot_background)
    plot_item = plot.getPlotItem()
    if grid:
        plot_item.showGrid(x=True, y=True, alpha=settings.grid_alpha)
    tick_font = QFont()
    tick_font.setPixelSize(settings.axis_text_px)
    axis_pen = pg.mkPen(settings.grid_color, width=1)
    text_pen = pg.mkPen(settings.axis_text_color, width=1)
    for axis_name in ("left", "bottom", "right", "top"):
        axis = plot_item.getAxis(axis_name)
        axis.setPen(axis_pen)
        axis.setTextPen(text_pen)
        axis.setTickFont(tick_font)
