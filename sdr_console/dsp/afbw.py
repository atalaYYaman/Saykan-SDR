"""Audio-frequency bandwidth (AFBW) limiting — post-demodulation low-pass.

Independent of the RF channel filter. Applied after demodulation (and FM
de-emphasis when present), before AGC / soft-limit. Defaults are mode-specific
and live on demodulator classes; this module stays mode-agnostic.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.signal import firwin, lfilter, lfilter_zi

from sdr_console.dsp.channelizer import PASSTHROUGH_TAPS

MIN_AFBW_TAPS = 15
MAX_AFBW_TAPS = 255
_TAPS_PER_TRANSITION = 3.3
# Relative transition width when Nyquist leaves little room.
_FALLBACK_TRANSITION_RATIO = 0.25

# Sensible absolute bounds for a UI spin / config sanitize.
MIN_AFBW_HZ = 100.0
MAX_AFBW_HZ = 20_000.0

# Common presets (Hz).
AFBW_SPEECH_HZ = 4_000.0
AFBW_SSB_HZ = 3_000.0
AFBW_CW_HZ = 1_000.0
AFBW_WFM_HZ = 15_000.0
AFBW_CHOICES_HZ: tuple[float, ...] = (
    500.0,
    1_000.0,
    2_700.0,
    3_000.0,
    4_000.0,
    6_000.0,
    10_000.0,
    15_000.0,
)


def design_afbw_lpf(
    cutoff_hz: float,
    sample_rate_hz: float,
    num_taps: int | None = None,
    window: str = "hamming",
) -> np.ndarray:
    """FIR low-pass taps with passband ending at ``cutoff_hz``.

    Returns a single unity tap when the cutoff reaches Nyquist (no filtering).
    """
    if cutoff_hz <= 0.0:
        raise ValueError("cutoff_hz must be positive")
    if sample_rate_hz <= 0.0:
        raise ValueError("sample_rate_hz must be positive")

    nyquist = sample_rate_hz / 2.0
    if cutoff_hz >= nyquist:
        return PASSTHROUGH_TAPS.copy()

    transition_hz = min(cutoff_hz * _FALLBACK_TRANSITION_RATIO, nyquist - cutoff_hz)
    if transition_hz <= 0.0:
        transition_hz = cutoff_hz * _FALLBACK_TRANSITION_RATIO

    if num_taps is None:
        estimated = int(math.ceil(_TAPS_PER_TRANSITION * sample_rate_hz / transition_hz))
        num_taps = min(max(estimated, MIN_AFBW_TAPS), MAX_AFBW_TAPS)
    if num_taps <= 0:
        raise ValueError("num_taps must be positive")
    if num_taps % 2 == 0:
        num_taps += 1

    return firwin(num_taps, cutoff_hz, fs=sample_rate_hz, window=window).astype(np.float64)


class AudioBandwidthFilter:
    """Stateful FIR AFBW filter for streaming float audio blocks."""

    def __init__(self, cutoff_hz: float, sample_rate_hz: float) -> None:
        if cutoff_hz <= 0.0:
            raise ValueError("cutoff_hz must be positive")
        if sample_rate_hz <= 0.0:
            raise ValueError("sample_rate_hz must be positive")

        self._cutoff_hz = float(cutoff_hz)
        self._sample_rate_hz = float(sample_rate_hz)
        self._taps = design_afbw_lpf(self._cutoff_hz, self._sample_rate_hz)
        self._state: np.ndarray | None = None

    @property
    def cutoff_hz(self) -> float:
        return self._cutoff_hz

    @property
    def sample_rate_hz(self) -> float:
        return self._sample_rate_hz

    @property
    def taps(self) -> np.ndarray:
        return self._taps

    def reset(self) -> None:
        self._state = None

    def process(self, samples: np.ndarray) -> np.ndarray:
        """Filter one block; returns float64 (caller converts / limits)."""
        if samples.size == 0:
            return np.zeros(0, dtype=np.float64)
        if self._taps.size == 1:
            return np.asarray(samples, dtype=np.float64) * float(self._taps[0])

        if self._state is None:
            self._state = lfilter_zi(self._taps, [1.0]) * float(samples[0])
        filtered, self._state = lfilter(self._taps, [1.0], samples, zi=self._state)
        return filtered
