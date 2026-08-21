"""Display tuning parameters for spectrum and waterfall widgets."""

from dataclasses import dataclass

# MASTER §6.1 — hex copied so viz does not import the UI theme package.
PLOT_BACKGROUND = "#0F172A"
AXIS_TEXT = "#94A3B8"
GRID_COLOR = "#334155"
SPECTRUM_PEN_CYAN = "#06B6D4"
SPECTRUM_PEN_AMBER = "#F59E0B"
CHANNEL_FILL = "#06B6D4"
CHANNEL_CENTER_LINE = "#EF4444"


@dataclass(frozen=True)
class DisplaySettings:
    """Colormap and dB scaling shared by viz widgets."""

    vmin_db: float = -80.0
    vmax_db: float = 0.0
    colormap: str = "viridis"
    history_rows: int = 200
    refresh_ms: int = 33
    spectrum_plot_height: int = 180
    # Fixed left-axis width keeps the spectrum and waterfall plot areas aligned
    # pixel-for-pixel even though only the spectrum shows dB tick labels.
    axis_label_width: int = 64
    plot_background: str = PLOT_BACKGROUND
    axis_text_color: str = AXIS_TEXT
    axis_text_px: int = 11
    grid_color: str = GRID_COLOR
    grid_alpha: float = 0.6
    spectrum_pen_color: str = SPECTRUM_PEN_CYAN
    channel_fill_color: str = CHANNEL_FILL
    channel_fill_alpha: int = 55
    channel_line_color: str = CHANNEL_CENTER_LINE
