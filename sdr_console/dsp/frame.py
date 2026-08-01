"""Structured spectrum rows passed from DSP to visualization."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SpectrumFrame:
    """One processed spectrum row for waterfall rendering.

    ``db_values`` is write-protected (dBFS). Callers must not mutate it.
    """

    db_values: np.ndarray
    center_freq: float
    sample_rate: float
    timestamp: float
