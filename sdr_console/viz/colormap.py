"""Colormap helpers for pyqtgraph image rendering."""

import pyqtgraph as pg


def apply_colormap(image_item: pg.ImageItem, colormap_name: str) -> None:
    """Apply a named matplotlib-compatible colormap to an ``ImageItem``."""
    color_map = pg.colormap.get(colormap_name, source="matplotlib")
    image_item.setColorMap(color_map)


def apply_db_levels(image_item: pg.ImageItem, vmin_db: float, vmax_db: float) -> None:
    """Set fixed dB display limits on an ``ImageItem``."""
    image_item.setLevels([vmin_db, vmax_db])
