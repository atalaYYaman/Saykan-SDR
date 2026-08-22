"""pytest-qt tests for the shared frequency axis and channel overlay."""

from __future__ import annotations

import numpy as np
import pytest

from sdr_console.dsp.channel import ChannelSpec
from sdr_console.dsp.frame import SpectrumFrame
from sdr_console.pipeline.sample_queue import SampleQueue
from sdr_console.viz.sdr_display import SdrDisplayWidget
from sdr_console.viz.settings import DisplaySettings

pytest.importorskip("pytestqt")

FFT_SIZE = 64
CENTER_HZ = 100_000_000.0
SAMPLE_RATE_HZ = 2_048_000.0


@pytest.fixture
def display(qtbot):
    widget = SdrDisplayWidget(
        fft_size=FFT_SIZE,
        settings=DisplaySettings(history_rows=8, spectrum_plot_height=80),
        center_freq_hz=CENTER_HZ,
        sample_rate_hz=SAMPLE_RATE_HZ,
        channel=ChannelSpec(CENTER_HZ, 200_000.0),
    )
    qtbot.addWidget(widget)
    return widget


def _frame(level_db: float, center_hz: float = CENTER_HZ, rate_hz: float = SAMPLE_RATE_HZ):
    values = np.full(FFT_SIZE, level_db, dtype=np.float64)
    values.setflags(write=False)
    return SpectrumFrame(
        db_values=values,
        center_freq=center_hz,
        sample_rate=rate_hz,
        timestamp=0.0,
    )


def test_plots_share_the_same_x_range(display: SdrDisplayWidget) -> None:
    spectrum_x = display.spectrum.getPlotItem().getViewBox().viewRange()[0]
    waterfall_x = display.waterfall.getPlotItem().getViewBox().viewRange()[0]

    assert spectrum_x == pytest.approx(waterfall_x)
    assert spectrum_x[0] == pytest.approx(CENTER_HZ - SAMPLE_RATE_HZ / 2.0)
    assert spectrum_x[1] == pytest.approx(CENTER_HZ + SAMPLE_RATE_HZ / 2.0)


def test_axes_stay_linked_when_one_plot_is_zoomed(display: SdrDisplayWidget) -> None:
    display.spectrum.setXRange(CENTER_HZ - 100_000.0, CENTER_HZ + 100_000.0, padding=0)

    waterfall_x = display.waterfall.getPlotItem().getViewBox().viewRange()[0]

    assert waterfall_x[0] == pytest.approx(CENTER_HZ - 100_000.0)
    assert waterfall_x[1] == pytest.approx(CENTER_HZ + 100_000.0)


def test_left_axis_widths_match_so_plot_areas_align(display: SdrDisplayWidget) -> None:
    spectrum_axis = display.spectrum.getPlotItem().getAxis("left")
    waterfall_axis = display.waterfall.getPlotItem().getAxis("left")

    assert spectrum_axis.width() == waterfall_axis.width()


def test_overlay_follows_the_selected_channel(display: SdrDisplayWidget) -> None:
    display.set_channel(ChannelSpec(CENTER_HZ + 300_000.0, 125_000.0))

    for overlay in display._overlays:
        low_hz, high_hz = overlay.region.getRegion()
        assert low_hz == pytest.approx(CENTER_HZ + 300_000.0 - 62_500.0)
        assert high_hz == pytest.approx(CENTER_HZ + 300_000.0 + 62_500.0)


def test_jam_band_hidden_until_set(display: SdrDisplayWidget) -> None:
    for overlay in display._jam_overlays:
        assert not overlay.region.isVisible()
    display.set_jam_band(ChannelSpec(CENTER_HZ, 500_000.0))
    for overlay in display._jam_overlays:
        assert overlay.region.isVisible()
        low_hz, high_hz = overlay.region.getRegion()
        assert high_hz - low_hz == pytest.approx(500_000.0)
    display.clear_jam_band()
    for overlay in display._jam_overlays:
        assert not overlay.region.isVisible()


def test_setting_the_channel_programmatically_does_not_emit_channel_moved(
    display: SdrDisplayWidget,
    qtbot,
) -> None:
    with qtbot.assertNotEmitted(display.channel_moved):
        display.set_channel(ChannelSpec(CENTER_HZ + 400_000.0, 200_000.0))


def test_dragging_the_overlay_emits_the_new_center(
    display: SdrDisplayWidget,
    qtbot,
) -> None:
    target_hz = CENTER_HZ + 500_000.0

    with qtbot.waitSignal(display.channel_moved, timeout=1000) as blocker:
        display._overlays[0].region.setRegion(
            (target_hz - 100_000.0, target_hz + 100_000.0)
        )

    assert blocker.args[0] == pytest.approx(target_hz)


def test_plot_click_is_forwarded_as_frequency_selected(
    display: SdrDisplayWidget,
    qtbot,
) -> None:
    with qtbot.waitSignal(display.frequency_selected, timeout=1000) as blocker:
        display.waterfall.frequency_clicked.emit(CENTER_HZ + 250_000.0)

    assert blocker.args[0] == pytest.approx(CENTER_HZ + 250_000.0)


def test_poll_queue_adopts_tuning_from_frames(display: SdrDisplayWidget) -> None:
    queue: SampleQueue[SpectrumFrame] = SampleQueue(maxsize=4)
    queue.put_drop_oldest(_frame(-50.0, center_hz=433_920_000.0, rate_hz=1_024_000.0))

    display.poll_queue(queue)

    assert display.spectrum.center_freq_hz == pytest.approx(433_920_000.0)
    assert display.waterfall.sample_rate_hz == pytest.approx(1_024_000.0)
    spectrum_x = display.spectrum.getPlotItem().getViewBox().viewRange()[0]
    assert spectrum_x[0] == pytest.approx(433_920_000.0 - 512_000.0)


def test_waterfall_image_spans_the_frequency_axis(display: SdrDisplayWidget) -> None:
    rect = display.waterfall._image.boundingRect()
    mapped = display.waterfall._image.mapRectToView(rect)

    assert mapped.left() == pytest.approx(CENTER_HZ - SAMPLE_RATE_HZ / 2.0)
    assert mapped.right() == pytest.approx(CENTER_HZ + SAMPLE_RATE_HZ / 2.0)
