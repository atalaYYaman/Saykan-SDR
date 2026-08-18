"""Spectrum frame averaging for dwell integration."""

from __future__ import annotations

import numpy as np

from sdr_console.dsp.frame import SpectrumFrame


class SpectrumAverager:
    """Accumulate multiple spectrum rows and emit a linear-power average."""

    def __init__(self, frame_count: int) -> None:
        if frame_count < 1:
            raise ValueError("frame_count must be at least 1")
        self._frame_count = frame_count
        self._power_sum: np.ndarray | None = None
        self._count = 0
        self._template: SpectrumFrame | None = None

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def collected_count(self) -> int:
        return self._count

    def reset(self) -> None:
        self._power_sum = None
        self._count = 0
        self._template = None

    def add(self, frame: SpectrumFrame) -> bool:
        """Add one frame. Returns True when the configured count is reached."""
        linear_power = np.power(10.0, frame.db_values / 10.0, dtype=np.float64)
        if self._power_sum is None:
            self._power_sum = np.zeros_like(linear_power, dtype=np.float64)
            self._template = frame

        if linear_power.shape != self._power_sum.shape:
            raise ValueError("all frames must have the same FFT size")

        self._power_sum += linear_power
        self._count += 1
        return self._count >= self._frame_count

    def result(self) -> SpectrumFrame | None:
        """Return the averaged frame, or None if nothing was collected."""
        if self._power_sum is None or self._template is None or self._count == 0:
            return None

        averaged_db = (10.0 * np.log10(np.maximum(self._power_sum / self._count, 1e-30))).astype(
            np.float64
        )
        averaged_db.setflags(write=False)
        return SpectrumFrame(
            db_values=averaged_db,
            center_freq=self._template.center_freq,
            sample_rate=self._template.sample_rate,
            timestamp=self._template.timestamp,
        )
