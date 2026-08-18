"""Digital signal processing — pure numpy/scipy functions."""

from sdr_console.dsp.afbw import (
    AFBW_CHOICES_HZ,
    AFBW_SPEECH_HZ,
    AFBW_WFM_HZ,
    AudioBandwidthFilter,
    design_afbw_lpf,
)
from sdr_console.dsp.agc import (
    AGC_PRESET_CHOICES,
    AgcPreset,
    AutomaticGainControl,
)
from sdr_console.dsp.audio import (
    AudioDecimationPlan,
    DemodChainPlan,
    apply_iir,
    choose_total_decimation,
    clip_audio,
    design_dc_blocker,
    plan_audio_decimation,
    plan_demod_chain,
    soft_limit_audio,
    split_decimation,
)
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
from sdr_console.dsp.deemphasis import (
    DEEMPHASIS_TAU_50_US,
    DEEMPHASIS_TAU_75_US,
    deemphasis_gain,
    design_deemphasis,
    preemphasis_gain,
    tau_seconds,
)
from sdr_console.dsp.frame import SpectrumFrame
from sdr_console.dsp.spectrum import (
    apply_window,
    compute_fft,
    compute_spectrum_frame,
    compute_waterfall_row,
    to_db,
)
from sdr_console.dsp.squelch import (
    ChannelSquelch,
    channel_power_db,
)

__all__ = [
    "AFBW_CHOICES_HZ",
    "AFBW_SPEECH_HZ",
    "AFBW_WFM_HZ",
    "AGC_PRESET_CHOICES",
    "MIN_CHANNEL_BANDWIDTH_HZ",
    "AgcPreset",
    "AudioBandwidthFilter",
    "AudioDecimationPlan",
    "AutomaticGainControl",
    "ChannelSpec",
    "ChannelSquelch",
    "DEEMPHASIS_TAU_50_US",
    "DEEMPHASIS_TAU_75_US",
    "DemodChainPlan",
    "ChannelizedBlock",
    "ChannelizerPlan",
    "ChannelizerState",
    "SpectrumFrame",
    "apply_iir",
    "apply_window",
    "band_edges_hz",
    "bin_to_freq_hz",
    "channel_power_db",
    "channelize",
    "choose_decimation",
    "choose_total_decimation",
    "clamp_freq_to_band",
    "clip_audio",
    "compute_fft",
    "compute_spectrum_frame",
    "compute_waterfall_row",
    "deemphasis_gain",
    "design_afbw_lpf",
    "design_channel_filter",
    "design_dc_blocker",
    "design_deemphasis",
    "filter_and_decimate",
    "freq_to_bin",
    "frequency_axis_hz",
    "frequency_shift",
    "plan_audio_decimation",
    "plan_channelizer",
    "plan_demod_chain",
    "preemphasis_gain",
    "soft_limit_audio",
    "split_decimation",
    "tau_seconds",
    "to_db",
]
