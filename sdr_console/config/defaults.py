"""Default runtime parameters for the SDR console."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AppDefaults:
    """Immutable default values used across layers."""

    sample_rate_hz: float = 2_048_000.0
    fft_size: int = 1024
    center_freq_hz: float = 100_000_000.0
    gain_db: float = 20.0
    mock_noise_amplitude: float = 0.05
    waterfall_history_rows: int = 200
    display_vmin_db: float = -80.0
    display_vmax_db: float = 0.0
    display_colormap: str = "viridis"
    display_refresh_ms: int = 33
    spectrum_plot_height: int = 180
    queue_maxsize: int = 32
    raw_queue_maxsize: int = 8
    device_uri: str = ""
    gain_mode: str = "manual"
    rx_buffer_size: int = 16_384
