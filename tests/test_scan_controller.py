"""Unit tests for band scan planning and execution."""

from __future__ import annotations

import time

import numpy as np
import pytest

from sdr_console.detect.tracker import SignalTracker
from sdr_console.dsp.axis import freq_to_bin
from sdr_console.dsp.frame import SpectrumFrame
from sdr_console.hal.mock_device import DEFAULT_CENTER_FREQ_HZ, MockSDRDevice, MockTone
from sdr_console.pipeline.pipeline import Pipeline
from sdr_console.pipeline.sample_queue import SampleQueue
from sdr_console.scan.controller import (
    ScanController,
    ScanMode,
    ScanProgress,
    centers_for_pass,
    compute_scan_centers,
    default_scan_step_hz,
    min_scan_step_hz,
)


def test_min_and_default_scan_step_track_sample_rate() -> None:
    sample_rate_hz = 2_048_000.0
    assert min_scan_step_hz(sample_rate_hz) == pytest.approx(sample_rate_hz / 2.0)
    assert default_scan_step_hz(sample_rate_hz) == pytest.approx(sample_rate_hz / 2.0)


def test_compute_scan_centers_single_step_when_span_fits_bandwidth() -> None:
    centers = compute_scan_centers(
        99_000_000.0,
        99_500_000.0,
        sample_rate_hz=2_048_000.0,
        step_hz=1_024_000.0,
    )

    assert centers == [pytest.approx(99_250_000.0)]


def test_compute_scan_centers_steps_with_overlap() -> None:
    sample_rate_hz = 2_000_000.0
    step_hz = 1_000_000.0
    centers = compute_scan_centers(
        100_000_000.0,
        110_000_000.0,
        sample_rate_hz=sample_rate_hz,
        step_hz=step_hz,
    )

    assert len(centers) >= 2
    assert centers[0] == pytest.approx(101_000_000.0)
    assert centers[-1] >= 109_000_000.0


def test_compute_scan_centers_rejects_step_below_half_sample_rate() -> None:
    with pytest.raises(ValueError, match="step_hz"):
        compute_scan_centers(
            100_000_000.0,
            101_000_000.0,
            sample_rate_hz=2_048_000.0,
            step_hz=500_000.0,
        )


def test_centers_for_pass_reverses_forward_list() -> None:
    forward = [101_000_000.0, 102_000_000.0, 103_000_000.0]
    assert centers_for_pass(forward, reverse=False) == forward
    assert centers_for_pass(forward, reverse=True) == list(reversed(forward))


def test_loop_mode_runs_forward_and_reverse_until_stopped() -> None:
    device = MockSDRDevice(realtime=False)
    step_hz = min_scan_step_hz(device.sample_rate_hz)
    forward_centers = compute_scan_centers(
        100_000_000.0,
        110_000_000.0,
        sample_rate_hz=device.sample_rate_hz,
        step_hz=step_hz,
    )
    assert len(forward_centers) >= 2
    pipeline = Pipeline(device=device, fft_size=1024, raw_queue_maxsize=4)
    scan_queue = pipeline.add_spectrum_consumer(maxsize=8)
    tracker = SignalTracker(consecutive_hits_required=1, match_tolerance_hz=10_000.0)
    progress_events: list[tuple[int, bool, float]] = []

    def on_progress(progress: ScanProgress) -> None:
        progress_events.append(
            (progress.round_index, progress.forward, progress.center_freq_hz)
        )

    controller = ScanController(
        device=device,
        frame_queue=scan_queue,
        tracker=tracker,
        fft_size=1024,
        start_freq_hz=100_000_000.0,
        end_freq_hz=110_000_000.0,
        step_hz=step_hz,
        threshold_db=-30.0,
        min_distance_hz=0.0,
        merge_bandwidth_hz=150_000.0,
        mode=ScanMode.LOOP,
        dwell_frames=1,
        flush_frames=1,
        settle_time_s=0.01,
        frame_timeout_s=1.0,
        on_progress=on_progress,
    )

    device.connect()
    pipeline.start()
    controller.start()

    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and controller.is_running:
        time.sleep(0.05)

    result = controller.stop()
    pipeline.stop()
    device.disconnect()
    pipeline.remove_spectrum_consumer(scan_queue)

    assert result is not None
    assert result.stopped_early
    assert progress_events
    assert max(event[0] for event in progress_events) >= 2
    assert any(event[1] for event in progress_events)
    assert any(not event[1] for event in progress_events)


def _synthetic_frame(
    peak_freq_hz: float,
    *,
    peak_power_db: float = -15.0,
    fft_size: int = 1024,
    center_freq_hz: float = 100_000_000.0,
    sample_rate_hz: float = 2_048_000.0,
) -> SpectrumFrame:
    db_values = np.full(fft_size, -80.0, dtype=np.float64)
    bin_index = freq_to_bin(peak_freq_hz, center_freq_hz, sample_rate_hz, fft_size)
    db_values[bin_index] = peak_power_db
    return SpectrumFrame(
        db_values=db_values,
        center_freq=center_freq_hz,
        sample_rate=sample_rate_hz,
        timestamp=0.0,
    )


def test_scan_controller_invokes_step_peaks_callback() -> None:
    tone_freq_hz = DEFAULT_CENTER_FREQ_HZ + 50_000.0
    device = MockSDRDevice(
        tones=(MockTone(tone_freq_hz, 1.0),),
        noise_amplitude=0.0,
        realtime=False,
    )
    pipeline = Pipeline(device=device, fft_size=1024, raw_queue_maxsize=4)
    scan_queue = pipeline.add_spectrum_consumer(maxsize=8)
    tracker = SignalTracker(consecutive_hits_required=3, match_tolerance_hz=10_000.0)
    step_callbacks: list[list] = []

    controller = ScanController(
        device=device,
        frame_queue=scan_queue,
        tracker=tracker,
        fft_size=1024,
        start_freq_hz=tone_freq_hz - 100_000.0,
        end_freq_hz=tone_freq_hz + 100_000.0,
        step_hz=min_scan_step_hz(device.sample_rate_hz),
        threshold_db=-30.0,
        min_distance_hz=0.0,
        merge_bandwidth_hz=150_000.0,
        dwell_frames=2,
        flush_frames=4,
        settle_time_s=0.05,
        frame_timeout_s=2.0,
        on_step_peaks=step_callbacks.append,
    )

    device.connect()
    pipeline.start()
    controller.start()

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and controller.is_running:
        time.sleep(0.05)

    if controller.is_running:
        controller.stop()

    pipeline.stop()
    device.disconnect()
    pipeline.remove_spectrum_consumer(scan_queue)

    assert step_callbacks
    assert all(isinstance(peaks, list) for peaks in step_callbacks)


def test_scan_controller_confirms_signals_without_candidate_stage() -> None:
    tone_freq_hz = DEFAULT_CENTER_FREQ_HZ + 50_000.0
    device = MockSDRDevice(
        tones=(MockTone(tone_freq_hz, 1.0),),
        noise_amplitude=0.0,
        realtime=False,
    )
    pipeline = Pipeline(device=device, fft_size=1024, raw_queue_maxsize=4)
    scan_queue = pipeline.add_spectrum_consumer(maxsize=8)
    tracker = SignalTracker(consecutive_hits_required=3, match_tolerance_hz=10_000.0)

    finished: list[object] = []

    controller = ScanController(
        device=device,
        frame_queue=scan_queue,
        tracker=tracker,
        fft_size=1024,
        start_freq_hz=tone_freq_hz - 100_000.0,
        end_freq_hz=tone_freq_hz + 100_000.0,
        step_hz=min_scan_step_hz(device.sample_rate_hz),
        threshold_db=-30.0,
        min_distance_hz=0.0,
        merge_bandwidth_hz=150_000.0,
        dwell_frames=2,
        flush_frames=4,
        settle_time_s=0.05,
        frame_timeout_s=2.0,
        on_finished=finished.append,
    )

    device.connect()
    pipeline.start()
    controller.start()

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and controller.is_running:
        time.sleep(0.05)

    if controller.is_running:
        controller.stop()

    pipeline.stop()
    device.disconnect()
    pipeline.remove_spectrum_consumer(scan_queue)

    confirmed = tracker.confirmed_signals()
    assert confirmed
    bin_width_hz = device.sample_rate_hz / 1024
    assert abs(confirmed[0].frequency_hz - tone_freq_hz) <= bin_width_hz
    assert finished


def test_scan_controller_lists_all_in_band_tones() -> None:
    center_hz = DEFAULT_CENTER_FREQ_HZ
    tones = (
        MockTone(center_hz - 75_000.0, 0.8),
        MockTone(center_hz + 50_000.0, 1.0),
        MockTone(center_hz + 250_000.0, 0.6),
    )
    device = MockSDRDevice(tones=tones, noise_amplitude=0.0, realtime=False)
    pipeline = Pipeline(device=device, fft_size=1024, raw_queue_maxsize=4)
    scan_queue = pipeline.add_spectrum_consumer(maxsize=8)
    tracker = SignalTracker(consecutive_hits_required=3, match_tolerance_hz=5_000.0)

    controller = ScanController(
        device=device,
        frame_queue=scan_queue,
        tracker=tracker,
        fft_size=1024,
        start_freq_hz=center_hz - 200_000.0,
        end_freq_hz=center_hz + 200_000.0,
        step_hz=min_scan_step_hz(device.sample_rate_hz),
        threshold_db=-40.0,
        min_distance_hz=0.0,
        merge_bandwidth_hz=50_000.0,
        dwell_frames=2,
        flush_frames=4,
        settle_time_s=0.05,
        frame_timeout_s=2.0,
    )

    device.connect()
    pipeline.start()
    controller.start()

    deadline = time.monotonic() + 6.0
    while time.monotonic() < deadline and controller.is_running:
        time.sleep(0.05)

    if controller.is_running:
        controller.stop()

    pipeline.stop()
    device.disconnect()
    pipeline.remove_spectrum_consumer(scan_queue)

    confirmed = tracker.confirmed_signals()
    assert len(confirmed) >= 2
    frequencies_hz = {signal.frequency_hz for signal in confirmed}
    bin_width_hz = device.sample_rate_hz / 1024
    assert any(abs(freq_hz - (center_hz - 75_000.0)) <= bin_width_hz for freq_hz in frequencies_hz)
    assert any(abs(freq_hz - (center_hz + 50_000.0)) <= bin_width_hz for freq_hz in frequencies_hz)
    assert not any(
        abs(freq_hz - (center_hz + 250_000.0)) <= bin_width_hz for freq_hz in frequencies_hz
    )
