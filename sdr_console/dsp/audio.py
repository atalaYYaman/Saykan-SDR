"""Audio-rate DSP primitives shared by all demodulators.

Pure functions with explicit state, same contract as ``channelizer``: anything
that must survive between blocks is passed in and returned.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import lfilter

from sdr_console.dsp.channelizer import (
    PASSTHROUGH_TAPS,
    ChannelizerPlan,
    design_channel_filter,
)

DEFAULT_AUDIO_RATE_HZ = 48_000.0
# Pass band as a fraction of the audio rate; the rest is the anti-alias
# transition up to audio_rate / 2.
AUDIO_PASSBAND_RATIO = 0.45
DEFAULT_DC_CUTOFF_HZ = 30.0
#: Factors allowed in the overall decimation so it splits into two stages well.
SMOOTH_PRIMES = (2, 3, 5, 7)
#: How far the audio rate may land from the preferred one to gain a better split.
TOTAL_DECIMATION_TOLERANCE = 0.2


@dataclass(frozen=True)
class AudioDecimationPlan:
    """Filter taps and decimation factor from an IF rate down to audio."""

    taps: np.ndarray
    decimation: int
    audio_rate_hz: float

    @property
    def num_taps(self) -> int:
        return int(self.taps.size)


def plan_audio_decimation(
    input_rate_hz: float,
    preferred_audio_rate_hz: float = DEFAULT_AUDIO_RATE_HZ,
    num_taps: int | None = None,
    decimation: int | None = None,
) -> AudioDecimationPlan:
    """Plan the step from ``input_rate_hz`` down to roughly the preferred rate.

    Only integer decimation is used, so the resulting ``audio_rate_hz`` is the
    closest achievable rate rather than exactly the preferred one. The audio sink
    is expected to open the output stream at that rate.

    Args:
        decimation: Forces a factor instead of deriving one from the preferred
            rate, for chains that must land on a rate decided elsewhere.
    """
    if input_rate_hz <= 0.0:
        raise ValueError("input_rate_hz must be positive")
    if preferred_audio_rate_hz <= 0.0:
        raise ValueError("preferred_audio_rate_hz must be positive")
    if decimation is not None and decimation < 1:
        raise ValueError("decimation must be at least 1")

    if decimation is None:
        decimation = max(1, int(round(input_rate_hz / preferred_audio_rate_hz)))
    audio_rate_hz = input_rate_hz / decimation

    if decimation == 1:
        taps = PASSTHROUGH_TAPS.copy()
    else:
        taps = design_channel_filter(
            2.0 * AUDIO_PASSBAND_RATIO * audio_rate_hz,
            input_rate_hz,
            audio_rate_hz,
            num_taps=num_taps,
        )

    return AudioDecimationPlan(
        taps=taps,
        decimation=decimation,
        audio_rate_hz=audio_rate_hz,
    )


@dataclass(frozen=True)
class DemodChainPlan:
    """Two-stage decimation: wideband IQ to IF, then IF to audio."""

    channel: ChannelizerPlan
    audio_decimation: int

    @property
    def if_rate_hz(self) -> float:
        return self.channel.output_rate_hz

    @property
    def audio_rate_hz(self) -> float:
        return self.channel.output_rate_hz / self.audio_decimation

    @property
    def total_decimation(self) -> int:
        return self.channel.decimation * self.audio_decimation


def is_smooth(value: int, primes: tuple[int, ...] = SMOOTH_PRIMES) -> bool:
    """Whether ``value`` factors entirely into ``primes``."""
    if value < 1:
        return False
    remaining = value
    for prime in primes:
        while remaining % prime == 0:
            remaining //= prime
    return remaining == 1


def choose_total_decimation(
    sample_rate_hz: float,
    preferred_audio_rate_hz: float = DEFAULT_AUDIO_RATE_HZ,
    tolerance: float = TOTAL_DECIMATION_TOLERANCE,
) -> int:
    """Pick the overall IQ-to-audio decimation for a sample rate.

    Prefers a factor-rich (7-smooth) number near the ideal ratio: the exact ratio
    is often prime, which would leave nothing to split between the channel and
    audio stages. Landing a few percent off the preferred audio rate costs
    nothing because the output stream is opened at whatever rate comes out.
    """
    if sample_rate_hz <= 0.0:
        raise ValueError("sample_rate_hz must be positive")
    if preferred_audio_rate_hz <= 0.0:
        raise ValueError("preferred_audio_rate_hz must be positive")

    ideal = sample_rate_hz / preferred_audio_rate_hz
    if ideal <= 1.0:
        return 1

    low = max(1, int(np.floor(ideal * (1.0 - tolerance))))
    high = max(low, int(np.ceil(ideal * (1.0 + tolerance))))
    candidates = range(low, high + 1)
    return min(candidates, key=lambda n: (not is_smooth(n), abs(n - ideal)))


def split_decimation(total: int, max_first: int) -> tuple[int, int]:
    """Split ``total`` into two factors, the first no larger than ``max_first``.

    Returns:
        ``(first, second)`` with ``first * second == total`` and ``first`` as
        large as ``max_first`` allows.
    """
    if total < 1:
        raise ValueError("total must be at least 1")
    if max_first < 1:
        raise ValueError("max_first must be at least 1")

    for first in range(min(total, max_first), 0, -1):
        if total % first == 0:
            return first, total // first
    return 1, total


def plan_demod_chain(
    sample_rate_hz: float,
    bandwidth_hz: float,
    preferred_audio_rate_hz: float = DEFAULT_AUDIO_RATE_HZ,
) -> DemodChainPlan:
    """Plan the whole IQ-to-audio decimation for one channel.

    The total decimation is fixed by the device sample rate alone, then split so
    the channel stage takes as much of it as the bandwidth allows. That keeps the
    audio rate constant while the user changes bandwidth or mode, so the audio
    stream never has to be reopened.
    """
    if sample_rate_hz <= 0.0:
        raise ValueError("sample_rate_hz must be positive")
    if bandwidth_hz <= 0.0:
        raise ValueError("bandwidth_hz must be positive")
    if preferred_audio_rate_hz <= 0.0:
        raise ValueError("preferred_audio_rate_hz must be positive")

    total = choose_total_decimation(sample_rate_hz, preferred_audio_rate_hz)
    max_if_decimation = max(1, int(sample_rate_hz // bandwidth_hz))
    if_decimation, audio_decimation = split_decimation(total, max_if_decimation)

    if_rate_hz = sample_rate_hz / if_decimation
    channel_plan = ChannelizerPlan(
        taps=design_channel_filter(bandwidth_hz, sample_rate_hz, if_rate_hz),
        decimation=if_decimation,
        output_rate_hz=if_rate_hz,
    )
    return DemodChainPlan(channel=channel_plan, audio_decimation=audio_decimation)


def design_dc_blocker(
    sample_rate_hz: float,
    cutoff_hz: float = DEFAULT_DC_CUTOFF_HZ,
) -> tuple[np.ndarray, np.ndarray]:
    """One-pole high-pass that strips the carrier DC from a detected envelope.

    Returns:
        ``(b, a)`` coefficients for :func:`apply_iir`.
    """
    if sample_rate_hz <= 0.0:
        raise ValueError("sample_rate_hz must be positive")
    if cutoff_hz <= 0.0:
        raise ValueError("cutoff_hz must be positive")

    pole = float(np.exp(-2.0 * np.pi * cutoff_hz / sample_rate_hz))
    b = np.array([1.0, -1.0], dtype=np.float64)
    a = np.array([1.0, -pole], dtype=np.float64)
    return b, a


def apply_iir(
    samples: np.ndarray,
    b: np.ndarray,
    a: np.ndarray,
    state: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Run an IIR filter, carrying its state across blocks.

    Returns:
        Filtered samples and the state for the next call.
    """
    order = max(a.size, b.size) - 1
    if order < 1:
        raise ValueError("filter must have at least first order")

    zi = state if state is not None else np.zeros(order, dtype=np.float64)
    filtered, next_state = lfilter(b, a, samples, zi=zi)
    return filtered, next_state


def clip_audio(samples: np.ndarray) -> np.ndarray:
    """Clamp audio to the [-1, 1] range expected by the audio sink."""
    return np.clip(samples, -1.0, 1.0).astype(np.float32, copy=False)
