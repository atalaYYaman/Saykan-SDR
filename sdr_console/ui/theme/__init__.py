"""Apply the MASTER.md dark console theme to a QApplication.

Call once per process. Safe to invoke from ``main()`` and ``MainWindow``.
Does not alter layout, pipeline, or pyqtgraph plot pens (Tur D).
"""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication

from sdr_console.ui.theme.palette import build_palette
from sdr_console.ui.theme.stylesheet import build_stylesheet

FUSION_STYLE = "Fusion"
_THEME_PROPERTY = "sdrConsoleThemeApplied"

__all__ = [
    "FUSION_STYLE",
    "apply_application_theme",
    "build_palette",
    "build_stylesheet",
    "theme_is_applied",
]


def theme_is_applied(app: QApplication | None = None) -> bool:
    application = app or QApplication.instance()
    if application is None:
        return False
    return bool(application.property(_THEME_PROPERTY))


def apply_application_theme(app: QApplication | None = None) -> bool:
    """Set Fusion + QPalette + QSS. Returns True if this call applied the theme."""
    application = app or QApplication.instance()
    if application is None:
        return False
    if theme_is_applied(application):
        return False
    application.setStyle(FUSION_STYLE)
    application.setPalette(build_palette())
    application.setStyleSheet(build_stylesheet())
    application.setProperty(_THEME_PROPERTY, True)
    return True
