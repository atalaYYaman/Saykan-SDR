"""Mouse-position helpers for frequency-axis plots."""

from __future__ import annotations

import pyqtgraph as pg
from PyQt6.QtCore import QPointF


def frequency_at_scene_pos(plot_widget: pg.PlotWidget, scene_pos: QPointF) -> float | None:
    """Map a scene position to the plot's x-axis value in Hz.

    Returns:
        Frequency in Hz, or ``None`` when the position is outside the plot area.
    """
    view_box = plot_widget.getPlotItem().getViewBox()
    if view_box is None:
        return None
    if not view_box.sceneBoundingRect().contains(scene_pos):
        return None

    return float(view_box.mapSceneToView(scene_pos).x())
