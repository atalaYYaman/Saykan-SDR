"""pytest-qt tests for spectrum/waterfall display polling."""

from __future__ import annotations

import numpy as np
import pytest

from sdr_console.dsp.frame import SpectrumFrame
from sdr_console.pipeline.sample_queue import SampleQueue
from sdr_console.viz.sdr_display import SdrDisplayWidget
from sdr_console.viz.settings import DisplaySettings

pytest.importorskip("pytestqt")


@pytest.fixture
def display(qtbot):
    widget = SdrDisplayWidget(
        fft_size=64,
        settings=DisplaySettings(history_rows=8, spectrum_plot_height=80),
    )
    qtbot.addWidget(widget)
    return widget


def _frame(values: np.ndarray) -> SpectrumFrame:
    arr = values.astype(np.float64)
    arr.setflags(write=False)
    return SpectrumFrame(
        db_values=arr,
        center_freq=100e6,
        sample_rate=2.048e6,
        timestamp=0.0,
    )


def test_poll_queue_refreshes_once_and_keeps_latest_row(
    display: SdrDisplayWidget,
    monkeypatch,
) -> None:
    queue: SampleQueue[SpectrumFrame] = SampleQueue(maxsize=8)
    refresh_calls = {"count": 0}
    original_refresh = display.waterfall.refresh

    def counting_refresh() -> None:
        refresh_calls["count"] += 1
        original_refresh()

    monkeypatch.setattr(display.waterfall, "refresh", counting_refresh)

    for level in (-70.0, -60.0, -50.0):
        queue.put_drop_oldest(_frame(np.full(64, level)))

    display.poll_queue(queue)

    assert refresh_calls["count"] == 1
    np.testing.assert_allclose(display.waterfall.history[-1], np.full(64, -50.0))
