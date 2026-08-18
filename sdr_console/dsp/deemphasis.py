"""FM broadcast de-emphasis: single-pole IIR ``H(s) = 1 / (1 + s·τ)``.

Pure functions — no demodulator or UI dependency. ``τ`` is typically 50 µs
(Europe/most of the world) or 75 µs (Americas/Korea).
"""

from __future__ import annotations

import math

import numpy as np

# Regional broadcast standards (seconds).
DEEMPHASIS_TAU_50_US: float = 50e-6
DEEMPHASIS_TAU_75_US: float = 75e-6
DEEMPHASIS_TAU_CHOICES_US: tuple[float, ...] = (50.0, 75.0)
DEFAULT_DEEMPHASIS_TAU_US: float = 75.0


def tau_seconds(tau_us: float) -> float:
    """Convert a microsecond time-constant to seconds."""
    if tau_us <= 0.0:
        raise ValueError("tau_us must be positive")
    return float(tau_us) * 1e-6


def deemphasis_gain(freq_hz: float, tau_s: float) -> float:
    """Continuous-time |H(f)| for ``1 / (1 + j·2π·f·τ)``."""
    if tau_s <= 0.0:
        raise ValueError("tau_s must be positive")
    return float(1.0 / math.sqrt(1.0 + (2.0 * math.pi * freq_hz * tau_s) ** 2))


def preemphasis_gain(freq_hz: float, tau_s: float) -> float:
    """Continuous-time |H_pre(f)| = ``|1 + j·2π·f·τ|`` (inverse of de-emphasis)."""
    if tau_s <= 0.0:
        raise ValueError("tau_s must be positive")
    return float(math.sqrt(1.0 + (2.0 * math.pi * freq_hz * tau_s) ** 2))


def design_deemphasis(
    sample_rate_hz: float,
    tau_s: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Design a one-pole IIR de-emphasis filter.

    Uses the impulse-invariant mapping of the continuous pole at ``-1/τ``:
    ``y[n] = (1 - p)·x[n] + p·y[n-1]`` with ``p = exp(-1/(τ·fs))``.

    Returns:
        ``(b, a)`` coefficients for :func:`sdr_console.dsp.audio.apply_iir`.
    """
    if sample_rate_hz <= 0.0:
        raise ValueError("sample_rate_hz must be positive")
    if tau_s <= 0.0:
        raise ValueError("tau_s must be positive")

    pole = float(math.exp(-1.0 / (tau_s * sample_rate_hz)))
    b = np.array([1.0 - pole], dtype=np.float64)
    a = np.array([1.0, -pole], dtype=np.float64)
    return b, a
