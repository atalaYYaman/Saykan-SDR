"""Pure buffer helpers for visualization (testable without Qt)."""

import numpy as np


def append_spectrum_row(history: np.ndarray, row: np.ndarray) -> None:
    """Scroll ``history`` up by one row and write ``row`` at the bottom in-place.

    Args:
        history: 2-D buffer shaped ``(history_rows, fft_size)``, modified in-place.
        row: 1-D dB spectrum row matching ``history`` width.
    """
    if row.shape[0] != history.shape[1]:
        raise ValueError("row width must match history column count")

    history[:-1] = history[1:]
    history[-1] = row.astype(history.dtype, copy=False)
