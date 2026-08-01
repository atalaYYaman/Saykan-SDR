"""Channel extraction: mix to baseband, low-pass filter, decimate.

Pure functions. Everything that has to survive across consecutive IQ blocks
(mixer phase, FIR delay line, decimation phase) is passed in and returned as
``ChannelizerState`` instead of being hidden in module state, so a worker thread
can stream blocks continuously and tests can process a signal in one shot.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.signal import firwin, lfilter

from sdr_console.dsp.channel import ChannelSpec

MIN_FILTER_TAPS = 15
MAX_FILTER_TAPS = 1_023
# Hamming-window transition-width rule of thumb: taps ~= 3.3 * fs / transition.
_TAPS_PER_TRANSITION = 3.3
# Used when the requested channel is as wide as the usable output band.
FALLBACK_TRANSITION_RATIO = 0.25

PASSTHROUGH_TAPS: np.ndarray = np.ones(1, dtype=np.float64)


@dataclass(frozen=True)
class ChannelizedBlock:
    """Baseband samples of one channel at the decimated rate."""

    samples: np.ndarray
    sample_rate_hz: float


@dataclass(frozen=True)
class ChannelizerState:
    """Carry-over state that keeps consecutive blocks gap- and click-free."""

    phase_rad: float = 0.0
    filter_state: np.ndarray | None = None
    decimation_offset: int = 0


@dataclass(frozen=True)
class ChannelizerPlan:
    """Filter taps and decimation factor for one channel bandwidth."""

    taps: np.ndarray
    decimation: int
    output_rate_hz: float

    @property
    def num_taps(self) -> int:
        return int(self.taps.size)


def choose_decimation(
    sample_rate_hz: float,
    bandwidth_hz: float,
    target_rate_hz: float,
) -> int:
    """Largest integer decimation that keeps the channel unaliased.

    The decimated rate stays at or above both ``bandwidth_hz`` (so the channel
    itself fits) and ``target_rate_hz`` (the rate the consumer asks for).
    """
    if sample_rate_hz <= 0.0:
        raise ValueError("sample_rate_hz must be positive")
    if bandwidth_hz <= 0.0:
        raise ValueError("bandwidth_hz must be positive")
    if target_rate_hz <= 0.0:
        raise ValueError("target_rate_hz must be positive")

    by_target = int(sample_rate_hz // target_rate_hz)
    by_bandwidth = int(sample_rate_hz // bandwidth_hz)
    return max(1, min(by_target, by_bandwidth))


def design_channel_filter(
    bandwidth_hz: float,
    sample_rate_hz: float,
    output_rate_hz: float,
    num_taps: int | None = None,
    window: str = "hamming",
) -> np.ndarray:
    """FIR low-pass taps for a channel of ``bandwidth_hz`` around baseband.

    The pass band ends at ``bandwidth_hz / 2``; the stop band must start by
    ``output_rate_hz / 2`` so that decimating to ``output_rate_hz`` does not fold
    energy back into the channel. The gap between the two sets the transition
    width and therefore the tap count.

    Returns:
        Float64 taps, or a single unity tap when no filtering is needed.
    """
    if bandwidth_hz <= 0.0:
        raise ValueError("bandwidth_hz must be positive")
    if sample_rate_hz <= 0.0:
        raise ValueError("sample_rate_hz must be positive")
    if output_rate_hz <= 0.0:
        raise ValueError("output_rate_hz must be positive")

    cutoff_hz = bandwidth_hz / 2.0
    if cutoff_hz >= sample_rate_hz / 2.0:
        return PASSTHROUGH_TAPS.copy()

    transition_hz = output_rate_hz / 2.0 - cutoff_hz
    if transition_hz <= 0.0:
        transition_hz = cutoff_hz * FALLBACK_TRANSITION_RATIO

    if num_taps is None:
        estimated = int(math.ceil(_TAPS_PER_TRANSITION * sample_rate_hz / transition_hz))
        num_taps = min(max(estimated, MIN_FILTER_TAPS), MAX_FILTER_TAPS)
    if num_taps <= 0:
        raise ValueError("num_taps must be positive")
    if num_taps % 2 == 0:
        num_taps += 1

    return firwin(num_taps, cutoff_hz, fs=sample_rate_hz, window=window).astype(np.float64)


def plan_channelizer(
    bandwidth_hz: float,
    sample_rate_hz: float,
    target_rate_hz: float,
    num_taps: int | None = None,
) -> ChannelizerPlan:
    """Build the decimation factor and matching anti-alias filter together."""
    decimation = choose_decimation(sample_rate_hz, bandwidth_hz, target_rate_hz)
    output_rate_hz = sample_rate_hz / decimation
    taps = design_channel_filter(
        bandwidth_hz,
        sample_rate_hz,
        output_rate_hz,
        num_taps=num_taps,
    )
    return ChannelizerPlan(taps=taps, decimation=decimation, output_rate_hz=output_rate_hz)


def frequency_shift(
    iq: np.ndarray,
    offset_hz: float,
    sample_rate_hz: float,
    start_phase_rad: float = 0.0,
) -> tuple[np.ndarray, float]:
    """Mix ``iq`` down so that ``offset_hz`` lands at DC.

    Args:
        iq: Complex IQ samples (1-D).
        offset_hz: Frequency of interest relative to the receiver center.
        sample_rate_hz: IQ sample rate.
        start_phase_rad: Mixer phase left over from the previous block.

    Returns:
        Shifted complex64 block and the phase to feed the next block.
    """
    if sample_rate_hz <= 0.0:
        raise ValueError("sample_rate_hz must be positive")
    if iq.size == 0:
        return iq.astype(np.complex64, copy=False), start_phase_rad

    phase_step = -2.0 * np.pi * float(offset_hz) / sample_rate_hz
    phase = start_phase_rad + phase_step * np.arange(iq.size, dtype=np.float64)
    mixed = iq * np.exp(1j * phase).astype(np.complex64)

    next_phase = math.fmod(start_phase_rad + phase_step * iq.size, 2.0 * np.pi)
    return mixed.astype(np.complex64, copy=False), next_phase


def filter_and_decimate(
    samples: np.ndarray,
    taps: np.ndarray,
    decimation: int,
    filter_state: np.ndarray | None = None,
    start_offset: int = 0,
) -> tuple[np.ndarray, np.ndarray | None, int]:
    """Low-pass ``samples`` with ``taps`` and keep every ``decimation``-th one.

    Works for complex IQ and for real audio; the output dtype follows the input.

    Args:
        samples: Complex or real samples to decimate.
        taps: FIR taps from :func:`design_channel_filter`.
        decimation: Integer downsampling factor (1 keeps every sample).
        filter_state: FIR delay line from the previous block.
        start_offset: Index of the first sample to keep, carried over so the
            decimation grid never slips between blocks.

    Returns:
        Decimated samples, the new filter state, and the offset for the next
        block.
    """
    if decimation < 1:
        raise ValueError("decimation must be at least 1")
    if taps.size == 0:
        raise ValueError("taps must not be empty")
    if not 0 <= start_offset < decimation:
        raise ValueError("start_offset must be in [0, decimation)")

    if taps.size == 1:
        filtered = samples * taps[0]
        next_state = filter_state
    else:
        zi = (
            filter_state
            if filter_state is not None
            else np.zeros(taps.size - 1, dtype=np.result_type(samples.dtype, taps.dtype))
        )
        filtered, next_state = lfilter(taps, 1.0, samples, zi=zi)

    decimated = filtered[start_offset::decimation]
    next_offset = (start_offset - samples.size) % decimation
    return np.ascontiguousarray(decimated), next_state, next_offset


def channelize(
    iq: np.ndarray,
    channel: ChannelSpec,
    device_center_freq_hz: float,
    sample_rate_hz: float,
    plan: ChannelizerPlan,
    state: ChannelizerState | None = None,
) -> tuple[ChannelizedBlock, ChannelizerState]:
    """Extract ``channel`` from a wideband IQ block.

    Mixes the channel to DC, removes everything outside its bandwidth, and
    decimates to ``plan.output_rate_hz``.

    Returns:
        The baseband block and the state to pass into the next call.
    """
    current = state or ChannelizerState()

    mixed, next_phase = frequency_shift(
        iq,
        channel.offset_from(device_center_freq_hz),
        sample_rate_hz,
        start_phase_rad=current.phase_rad,
    )
    samples, filter_state, next_offset = filter_and_decimate(
        mixed,
        plan.taps,
        plan.decimation,
        filter_state=current.filter_state,
        start_offset=current.decimation_offset,
    )

    block = ChannelizedBlock(
        samples=samples.astype(np.complex64, copy=False),
        sample_rate_hz=plan.output_rate_hz,
    )
    next_state = ChannelizerState(
        phase_rad=next_phase,
        filter_state=filter_state,
        decimation_offset=next_offset,
    )
    return block, next_state
