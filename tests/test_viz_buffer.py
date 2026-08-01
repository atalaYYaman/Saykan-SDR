"""Unit tests for viz buffer scrolling."""

import numpy as np
import pytest

from sdr_console.viz.buffer import append_spectrum_row


def test_append_spectrum_row_scrolls_and_writes_bottom_row() -> None:
    history = np.zeros((4, 3), dtype=np.float32)
    history[0] = [1, 1, 1]
    history[1] = [2, 2, 2]
    history[2] = [3, 3, 3]
    history[3] = [4, 4, 4]

    append_spectrum_row(history, np.array([9, 8, 7], dtype=np.float64))

    expected = np.array(
        [
            [2, 2, 2],
            [3, 3, 3],
            [4, 4, 4],
            [9, 8, 7],
        ],
        dtype=np.float32,
    )
    np.testing.assert_array_equal(history, expected)


def test_append_spectrum_row_rejects_width_mismatch() -> None:
    history = np.zeros((4, 3), dtype=np.float32)
    with pytest.raises(ValueError):
        append_spectrum_row(history, np.array([1.0, 2.0]))
