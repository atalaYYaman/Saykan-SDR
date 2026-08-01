"""Visualization helpers — prefer importing concrete modules.

Qt-heavy widgets are not re-exported here so that ``viz.buffer`` remains
importable without PyQt6/pyqtgraph in pure unit tests.
"""

from sdr_console.viz.buffer import append_spectrum_row
from sdr_console.viz.settings import DisplaySettings

__all__ = [
    "DisplaySettings",
    "append_spectrum_row",
]
