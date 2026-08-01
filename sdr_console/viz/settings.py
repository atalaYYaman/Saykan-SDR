"""Display tuning parameters for spectrum and waterfall widgets."""

from dataclasses import dataclass


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
    channel_fill_color: str = "#4dd0e1"
    channel_fill_alpha: int = 55
    channel_line_color: str = "#ff5252"
