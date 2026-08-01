"""Spectrum and waterfall row computation."""

from __future__ import annotations

import time

import numpy as np
from scipy.signal import get_window

from sdr_console.dsp.frame import SpectrumFrame

_DB_FLOOR = 1e-12


def _prepare_block(iq: np.ndarray, fft_size: int) -> np.ndarray:
    """Truncate or zero-pad ``iq`` to exactly ``fft_size`` samples."""
    if iq.size == 0:
        raise ValueError("iq must contain at least one sample")
    if iq.size >= fft_size:
        return iq[:fft_size]
    block = np.zeros(fft_size, dtype=np.complex64)
    block[: iq.size] = iq
    return block


def apply_window(iq: np.ndarray, window: str = "hann") -> np.ndarray:
    """Apply a window function to an IQ block.

    Args:
        iq: Complex IQ samples (1-D).
        window: SciPy window name passed to ``get_window``.

    Returns:
        Windowed complex array with the same shape as ``iq``.
    """
    if iq.size == 0:
        raise ValueError("iq must contain at least one sample")

    coeffs = get_window(window, iq.size, fftbins=True).astype(np.float32)
    return iq * coeffs


def _windowed_fft(
    iq: np.ndarray,
    fft_size: int,
    window: str = "hann",
) -> tuple[np.ndarray, float]:
    """Shared pipeline: prepare -> window -> FFT -> fftshift.

    Returns:
        Complex centered spectrum and coherent window gain (sum of coeffs).
    """
    block = _prepare_block(iq, fft_size)
    coeffs = get_window(window, fft_size, fftbins=True).astype(np.float64)
    windowed = block * coeffs.astype(np.float32)
    spectrum = np.fft.fftshift(np.fft.fft(windowed, n=fft_size))
    coherent_gain = float(np.sum(coeffs))
    return spectrum, coherent_gain


def compute_fft(iq: np.ndarray, fft_size: int, window: str = "hann") -> np.ndarray:
    """Compute a centered FFT of an IQ block (Hann window by default).

    Truncates or zero-pads ``iq`` to ``fft_size`` before transforming.

    Args:
        iq: Complex IQ samples (1-D).
        fft_size: Number of FFT bins.
        window: SciPy window name.

    Returns:
        Complex FFT output of length ``fft_size``, fftshift applied.
    """
    spectrum, _ = _windowed_fft(iq, fft_size, window=window)
    return spectrum


def to_db(spectrum: np.ndarray, ref: float = 1.0) -> np.ndarray:
    """Convert a complex or magnitude spectrum to decibels.

    Args:
        spectrum: Complex FFT bins or real magnitudes.
        ref: Reference amplitude for dB scaling (use window coherent gain for dBFS).

    Returns:
        One-dimensional float64 dB array.
    """
    if ref <= 0.0:
        raise ValueError("ref must be positive")

    magnitude = np.abs(spectrum) if np.iscomplexobj(spectrum) else np.asarray(spectrum)
    normalized = np.maximum(magnitude / ref, _DB_FLOOR)
    return (20.0 * np.log10(normalized)).astype(np.float64)


def compute_spectrum_frame(
    iq: np.ndarray,
    fft_size: int,
    center_freq: float,
    sample_rate: float,
    window: str = "hann",
    timestamp: float | None = None,
) -> SpectrumFrame:
    """Run the full IQ -> dBFS pipeline and wrap metadata in a frame."""
    spectrum, coherent_gain = _windowed_fft(iq, fft_size, window=window)
    db_values = to_db(spectrum, ref=coherent_gain)
    db_values.setflags(write=False)

    return SpectrumFrame(
        db_values=db_values,
        center_freq=center_freq,
        sample_rate=sample_rate,
        timestamp=time.time() if timestamp is None else timestamp,
    )


def compute_waterfall_row(
    iq: np.ndarray,
    fft_size: int,
    window: str = "hann",
) -> np.ndarray:
    """Convert IQ samples into one dBFS row (legacy helper without metadata)."""
    return compute_spectrum_frame(
        iq,
        fft_size=fft_size,
        center_freq=0.0,
        sample_rate=1.0,
        window=window,
        timestamp=0.0,
    ).db_values
