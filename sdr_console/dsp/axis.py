"""Frequency axis math shared by visualization and channel selection.

Pure functions only: no Qt, no hardware. Keeping the bin/Hz conversions here
lets the UI and viz layers work in absolute RF frequency without importing
numpy themselves.
"""

from __future__ import annotations

import numpy as np


def _validate_tuning(sample_rate_hz: float, fft_size: int) -> None:
    if fft_size <= 0:
        raise ValueError("fft_size must be positive")
    if sample_rate_hz <= 0.0:
        raise ValueError("sample_rate_hz must be positive")


def frequency_axis_hz(
    center_freq_hz: float,
    sample_rate_hz: float,
    fft_size: int,
) -> np.ndarray:
    """Absolute RF frequency of every bin in an fftshifted spectrum.

    Args:
        center_freq_hz: Receiver center frequency in Hz.
        sample_rate_hz: IQ sample rate in samples per second.
        fft_size: Number of FFT bins.

    Returns:
        Float64 array of length ``fft_size``, ascending in frequency.
    """
    _validate_tuning(sample_rate_hz, fft_size)

    offsets = np.fft.fftshift(np.fft.fftfreq(fft_size, d=1.0 / sample_rate_hz))
    return offsets + float(center_freq_hz)


def band_edges_hz(center_freq_hz: float, sample_rate_hz: float) -> tuple[float, float]:
    """Lowest and highest observable frequency for the current tuning."""
    if sample_rate_hz <= 0.0:
        raise ValueError("sample_rate_hz must be positive")

    half_span = sample_rate_hz / 2.0
    return (float(center_freq_hz) - half_span, float(center_freq_hz) + half_span)


def bin_to_freq_hz(
    bin_index: int,
    center_freq_hz: float,
    sample_rate_hz: float,
    fft_size: int,
) -> float:
    """Convert an fftshifted bin index to absolute frequency in Hz."""
    _validate_tuning(sample_rate_hz, fft_size)

    offset = (bin_index - fft_size // 2) * sample_rate_hz / fft_size
    return float(center_freq_hz) + offset


def freq_to_bin(
    freq_hz: float,
    center_freq_hz: float,
    sample_rate_hz: float,
    fft_size: int,
) -> int:
    """Convert absolute frequency to the nearest fftshifted bin index.

    The result is clamped to ``[0, fft_size - 1]`` so out-of-band requests stay
    usable for indexing.
    """
    _validate_tuning(sample_rate_hz, fft_size)

    offset_bins = (float(freq_hz) - float(center_freq_hz)) * fft_size / sample_rate_hz
    index = int(round(offset_bins)) + fft_size // 2
    return max(0, min(fft_size - 1, index))


def clamp_freq_to_band(
    freq_hz: float,
    center_freq_hz: float,
    sample_rate_hz: float,
) -> float:
    """Clamp ``freq_hz`` into the observable band around ``center_freq_hz``."""
    low_hz, high_hz = band_edges_hz(center_freq_hz, sample_rate_hz)
    return max(low_hz, min(high_hz, float(freq_hz)))
