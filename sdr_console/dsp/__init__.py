"""Digital signal processing — pure numpy/scipy functions."""

from sdr_console.dsp.axis import (
    band_edges_hz,
    bin_to_freq_hz,
    clamp_freq_to_band,
    freq_to_bin,
    frequency_axis_hz,
)
from sdr_console.dsp.channel import MIN_CHANNEL_BANDWIDTH_HZ, ChannelSpec
from sdr_console.dsp.frame import SpectrumFrame
from sdr_console.dsp.spectrum import (
    apply_window,
    compute_fft,
    compute_spectrum_frame,
    compute_waterfall_row,
    to_db,
)

__all__ = [
    "MIN_CHANNEL_BANDWIDTH_HZ",
    "ChannelSpec",
    "SpectrumFrame",
    "apply_window",
    "band_edges_hz",
    "bin_to_freq_hz",
    "clamp_freq_to_band",
    "compute_fft",
    "compute_spectrum_frame",
    "compute_waterfall_row",
    "freq_to_bin",
    "frequency_axis_hz",
    "to_db",
]
