"""Unit tests for spectrum frame averaging."""

from __future__ import annotations

import numpy as np
import pytest

from sdr_console.dsp.averager import SpectrumAverager
from sdr_console.dsp.frame import SpectrumFrame


def _frame(db_value: float, *, timestamp: float = 0.0) -> SpectrumFrame:
    db_values = np.full(8, db_value, dtype=np.float64)
    return SpectrumFrame(
        db_values=db_values,
        center_freq=100_000_000.0,
        sample_rate=2_048_000.0,
        timestamp=timestamp,
    )


def test_spectrum_averager_computes_linear_power_mean() -> None:
    averager = SpectrumAverager(2)
    assert not averager.add(_frame(-20.0, timestamp=0.0))
    assert averager.add(_frame(-26.0, timestamp=1.0))

    result = averager.result()
    assert result is not None
    assert result.timestamp == pytest.approx(0.0)
    expected_db = 10.0 * np.log10(
        (10 ** (-20.0 / 10.0) + 10 ** (-26.0 / 10.0)) / 2.0
    )
    assert result.db_values[0] == pytest.approx(expected_db)


def test_spectrum_averager_rejects_invalid_frame_count() -> None:
    with pytest.raises(ValueError, match="frame_count"):
        SpectrumAverager(0)
