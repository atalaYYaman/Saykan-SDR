"""Fusion QPalette mapped from MASTER semantic tokens."""

from __future__ import annotations

from PyQt6.QtGui import QColor, QPalette

from sdr_console.ui.theme.tokens import (
    COLOR_BG_APP,
    COLOR_BG_ELEVATED,
    COLOR_BG_INPUT,
    COLOR_BG_PANEL,
    COLOR_BORDER,
    COLOR_ED_ACCENT,
    COLOR_ET_ACCENT,
    COLOR_TEXT_DISABLED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    SLATE_600,
)


def _color(hex_value: str) -> QColor:
    color = QColor(hex_value)
    if not color.isValid():
        raise ValueError(f"Invalid theme color: {hex_value}")
    return color


def build_palette() -> QPalette:
    """Dark ED/ET console palette. Does not change pyqtgraph plot pens."""
    palette = QPalette()
    window = _color(COLOR_BG_APP)
    panel = _color(COLOR_BG_PANEL)
    text = _color(COLOR_TEXT_PRIMARY)
    secondary = _color(COLOR_TEXT_SECONDARY)
    disabled = _color(COLOR_TEXT_DISABLED)
    highlight = _color(COLOR_ED_ACCENT)
    highlight_text = _color(COLOR_BG_APP)
    base = _color(COLOR_BG_INPUT)
    alternate = _color(COLOR_BG_ELEVATED)
    mid = _color(COLOR_BORDER)
    button = panel
    bright = _color(COLOR_ET_ACCENT)

    active = QPalette.ColorGroup.Active
    inactive = QPalette.ColorGroup.Inactive
    disabled_group = QPalette.ColorGroup.Disabled

    for group in (active, inactive):
        palette.setColor(group, QPalette.ColorRole.Window, window)
        palette.setColor(group, QPalette.ColorRole.WindowText, text)
        palette.setColor(group, QPalette.ColorRole.Base, base)
        palette.setColor(group, QPalette.ColorRole.AlternateBase, alternate)
        palette.setColor(group, QPalette.ColorRole.ToolTipBase, panel)
        palette.setColor(group, QPalette.ColorRole.ToolTipText, text)
        palette.setColor(group, QPalette.ColorRole.Text, text)
        palette.setColor(group, QPalette.ColorRole.Button, button)
        palette.setColor(group, QPalette.ColorRole.ButtonText, text)
        palette.setColor(group, QPalette.ColorRole.BrightText, bright)
        palette.setColor(group, QPalette.ColorRole.Highlight, highlight)
        palette.setColor(group, QPalette.ColorRole.HighlightedText, highlight_text)
        palette.setColor(group, QPalette.ColorRole.Link, highlight)
        palette.setColor(group, QPalette.ColorRole.PlaceholderText, secondary)
        palette.setColor(group, QPalette.ColorRole.Light, _color(SLATE_600))
        palette.setColor(group, QPalette.ColorRole.Mid, mid)
        palette.setColor(group, QPalette.ColorRole.Dark, window)
        palette.setColor(group, QPalette.ColorRole.Shadow, window)

    palette.setColor(disabled_group, QPalette.ColorRole.Window, window)
    palette.setColor(disabled_group, QPalette.ColorRole.WindowText, disabled)
    palette.setColor(disabled_group, QPalette.ColorRole.Base, base)
    palette.setColor(disabled_group, QPalette.ColorRole.AlternateBase, alternate)
    palette.setColor(disabled_group, QPalette.ColorRole.Text, disabled)
    palette.setColor(disabled_group, QPalette.ColorRole.Button, button)
    palette.setColor(disabled_group, QPalette.ColorRole.ButtonText, disabled)
    palette.setColor(disabled_group, QPalette.ColorRole.Highlight, mid)
    palette.setColor(disabled_group, QPalette.ColorRole.HighlightedText, disabled)
    palette.setColor(disabled_group, QPalette.ColorRole.PlaceholderText, disabled)
    palette.setColor(disabled_group, QPalette.ColorRole.Mid, mid)
    return palette
