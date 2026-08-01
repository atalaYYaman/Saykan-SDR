"""Digital signal processing — pure numpy/scipy functions."""

from sdr_console.dsp.axis import (
    band_edges_hz,
    bin_to_freq_hz,
    clamp_freq_to_band,
    freq_to_bin,
    frequency_axis_hz,
)
from sdr_console.dsp.channel import MIN_CHANNEL_BANDWIDTH_HZ, ChannelSpec
from sdr_console.dsp.channelizer import (
    ChannelizedBlock,
    ChannelizerPlan,
    ChannelizerState,
    channelize,
    choose_decimation,
    design_channel_filter,
    filter_and_decimate,
    frequency_shift,
    plan_channelizer,
)
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
    "ChannelizedBlock",
    "ChannelizerPlan",
    "ChannelizerState",
    "SpectrumFrame",
    "apply_window",
    "band_edges_hz",
    "bin_to_freq_hz",
    "channelize",
    "choose_decimation",
    "clamp_freq_to_band",
    "compute_fft",
    "compute_spectrum_frame",
    "compute_waterfall_row",
    "design_channel_filter",
    "filter_and_decimate",
    "freq_to_bin",
    "frequency_axis_hz",
    "frequency_shift",
    "plan_channelizer",
    "to_db",
]
