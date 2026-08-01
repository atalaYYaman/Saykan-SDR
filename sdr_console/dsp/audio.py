"""Audio-rate DSP primitives shared by all demodulators.

Pure functions with explicit state, same contract as ``channelizer``: anything
that must survive between blocks is passed in and returned.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import lfilter

from sdr_console.dsp.channelizer import PASSTHROUGH_TAPS, design_channel_filter

DEFAULT_AUDIO_RATE_HZ = 48_000.0
# Pass band as a fraction of the audio rate; the rest is the anti-alias
# transition up to audio_rate / 2.
AUDIO_PASSBAND_RATIO = 0.45
DEFAULT_DC_CUTOFF_HZ = 30.0


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
) -> AudioDecimationPlan:
    """Plan the step from ``input_rate_hz`` down to roughly the preferred rate.

    Only integer decimation is used, so the resulting ``audio_rate_hz`` is the
    closest achievable rate rather than exactly the preferred one. The audio sink
    is expected to open the output stream at that rate.
    """
    if input_rate_hz <= 0.0:
        raise ValueError("input_rate_hz must be positive")
    if preferred_audio_rate_hz <= 0.0:
        raise ValueError("preferred_audio_rate_hz must be positive")

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
