"""Tur D: pyqtgraph palette follows design-system/MASTER.md §6.1."""

from __future__ import annotations

import pytest

from sdr_console.viz.sdr_display import SdrDisplayWidget
from sdr_console.viz.settings import (
    CHANNEL_CENTER_LINE,
    CHANNEL_FILL,
    PLOT_BACKGROUND,
    SPECTRUM_PEN_CYAN,
    DisplaySettings,
)

pytest.importorskip("pytestqt")


def test_display_settings_defaults_match_master_tokens() -> None:
    settings = DisplaySettings()
    assert settings.plot_background == PLOT_BACKGROUND == "#0F172A"
    assert settings.axis_text_color == "#94A3B8"
    assert settings.grid_color == "#334155"
    assert settings.grid_alpha == pytest.approx(0.6)
    assert settings.spectrum_pen_color == SPECTRUM_PEN_CYAN == "#06B6D4"
    assert settings.channel_fill_color == CHANNEL_FILL
    assert settings.channel_line_color == CHANNEL_CENTER_LINE == "#EF4444"
    assert settings.colormap == "viridis"
    assert settings.vmin_db == -80.0
    assert settings.vmax_db == 0.0
    assert settings.spectrum_plot_height == 180


def test_spectrum_curve_uses_ed_cyan_pen(qtbot) -> None:
    widget = SdrDisplayWidget(
        fft_size=64,
        settings=DisplaySettings(history_rows=8, spectrum_plot_height=80),
    )
    qtbot.addWidget(widget)
    pen = widget.spectrum._curve.opts["pen"]
    color = pen.color().name() if hasattr(pen, "color") else str(pen)
    assert SPECTRUM_PEN_CYAN.lower() in color.lower()


def test_plot_background_is_app_navy(qtbot) -> None:
    widget = SdrDisplayWidget(
        fft_size=64,
        settings=DisplaySettings(history_rows=8, spectrum_plot_height=80),
    )
    qtbot.addWidget(widget)
    bg = widget.spectrum.backgroundBrush().color().name()
    assert bg.lower() == PLOT_BACKGROUND.lower()
