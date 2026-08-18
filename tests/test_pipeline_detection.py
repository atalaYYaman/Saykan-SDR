"""Unit tests for detection pipeline integration."""

from __future__ import annotations

import time

import numpy as np
import pytest

from sdr_console.detect.peaks import detect_peaks, merge_nearby_peaks
from sdr_console.dsp.axis import freq_to_bin
from sdr_console.dsp.frame import SpectrumFrame
from sdr_console.hal.mock_device import DEFAULT_CENTER_FREQ_HZ, MockSDRDevice, MockTone
from sdr_console.pipeline.detection_worker import DetectionWorker
from sdr_console.pipeline.pipeline import Pipeline
from sdr_console.pipeline.processing_worker import ProcessingWorker
from sdr_console.pipeline.sample_queue import SampleQueue


def _synthetic_frame(
    peak_freq_hz: float,
    *,
    peak_power_db: float = -15.0,
    floor_db: float = -80.0,
    fft_size: int = 1024,
    center_freq_hz: float = 100_000_000.0,
    sample_rate_hz: float = 2_048_000.0,
    timestamp: float = 0.0,
) -> SpectrumFrame:
    db_values = np.full(fft_size, floor_db, dtype=np.float64)
    bin_index = freq_to_bin(peak_freq_hz, center_freq_hz, sample_rate_hz, fft_size)
    db_values[bin_index] = peak_power_db
    return SpectrumFrame(
        db_values=db_values,
        center_freq=center_freq_hz,
        sample_rate=sample_rate_hz,
        timestamp=timestamp,
    )


def test_processing_worker_fans_out_frames_to_extra_consumers() -> None:
    device = MockSDRDevice(
        tones=(MockTone(DEFAULT_CENTER_FREQ_HZ + 50_000.0, 1.0),),
        noise_amplitude=0.0,
        realtime=False,
    )
    raw_queue: SampleQueue[np.ndarray] = SampleQueue(maxsize=4)
    primary_queue: SampleQueue[SpectrumFrame] = SampleQueue(maxsize=4)
    secondary_queue: SampleQueue[SpectrumFrame] = SampleQueue(maxsize=4)
    worker = ProcessingWorker(
        device=device,
        raw_queue=raw_queue,
        output_queue=primary_queue,
        fft_size=512,
    )
    worker.add_consumer(secondary_queue)

    device.connect()
    worker.start()
    raw_queue.put_drop_oldest(device.read_samples(512))

    deadline = time.monotonic() + 2.0
    primary_frame = None
    secondary_frame = None
    while time.monotonic() < deadline:
        if primary_frame is None:
            primary_frame = primary_queue.try_get(timeout=0.05)
        if secondary_frame is None:
            secondary_frame = secondary_queue.try_get(timeout=0.05)
        if primary_frame is not None and secondary_frame is not None:
            break

    worker.stop()
    device.disconnect()

    assert primary_frame is not None
    assert secondary_frame is not None
    np.testing.assert_array_equal(primary_frame.db_values, secondary_frame.db_values)


def test_detection_worker_skips_processing_when_disabled() -> None:
    input_queue: SampleQueue[SpectrumFrame] = SampleQueue(maxsize=4)
    worker = DetectionWorker(
        input_queue=input_queue,
        window_frames=2,
        confirm_hits=1,
    )

    worker.start()
    input_queue.put_drop_oldest(_synthetic_frame(100_050_000.0))
    time.sleep(0.2)

    assert worker.state.snapshot() == []
    worker.stop()


def test_detection_worker_publishes_confirmed_peaks_when_enabled() -> None:
    input_queue: SampleQueue[SpectrumFrame] = SampleQueue(maxsize=8)
    worker = DetectionWorker(
        input_queue=input_queue,
        threshold_db=-40.0,
        window_frames=3,
        confirm_hits=2,
    )
    worker.set_enabled(True)
    worker.start()

    for timestamp in (0.0, 1.0, 2.0):
        input_queue.put_drop_oldest(
            _synthetic_frame(100_050_000.0, timestamp=timestamp),
        )

    deadline = time.monotonic() + 2.0
    peaks = []
    while time.monotonic() < deadline:
        peaks = worker.state.snapshot()
        if peaks:
            break
        time.sleep(0.05)

    worker.stop()

    assert len(peaks) == 1
    assert peaks[0].frequency_hz == pytest.approx(100_050_000.0, rel=1e-5)
    assert peaks[0].power_db == pytest.approx(-15.0)


def test_detection_worker_clear_all_clears_published_state() -> None:
    input_queue: SampleQueue[SpectrumFrame] = SampleQueue(maxsize=4)
    worker = DetectionWorker(
        input_queue=input_queue,
        confirm_hits=1,
    )
    worker.set_enabled(True)
    worker.start()
    input_queue.put_drop_oldest(_synthetic_frame(99_900_000.0))

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and not worker.state.snapshot():
        time.sleep(0.05)

    assert worker.state.snapshot()

    worker.clear_all()
    assert worker.state.snapshot() == []
    worker.stop()


def test_pipeline_attach_detection_receives_spectrum_frames() -> None:
    device = MockSDRDevice(
        tones=(MockTone(DEFAULT_CENTER_FREQ_HZ + 50_000.0, 1.0),),
        noise_amplitude=0.0,
        realtime=False,
    )
    pipeline = Pipeline(device=device, fft_size=1024, raw_queue_maxsize=4)
    detection = pipeline.attach_detection(
        window_frames=2,
        confirm_hits=1,
        threshold_db=-30.0,
    )
    detection.set_enabled(True)

    device.connect()
    pipeline.start()

    deadline = time.monotonic() + 3.0
    peaks = []
    while time.monotonic() < deadline:
        peaks = detection.state.snapshot()
        if peaks:
            break
        time.sleep(0.05)

    pipeline.stop()
    device.disconnect()

    assert peaks
    assert peaks[0].power_db >= -30.0


def test_detection_worker_captures_device_gain_at_confirmation() -> None:
    from sdr_console.hal.mock_device import MockSDRDevice

    device = MockSDRDevice(gain_db=42.5, realtime=False)
    input_queue: SampleQueue[SpectrumFrame] = SampleQueue(maxsize=8)
    worker = DetectionWorker(
        input_queue=input_queue,
        device=device,
        confirm_hits=3,
        threshold_db=-40.0,
    )
    worker.set_enabled(True)
    worker.start()

    frame = _synthetic_frame(100_050_000.0)
    for timestamp in (0.0, 1.0, 2.0):
        input_queue.put_drop_oldest(
            SpectrumFrame(
                db_values=frame.db_values,
                center_freq=frame.center_freq,
                sample_rate=frame.sample_rate,
                timestamp=timestamp,
            )
        )

    deadline = time.monotonic() + 2.0
    peaks = []
    while time.monotonic() < deadline:
        peaks = worker.state.snapshot()
        if peaks:
            break
        time.sleep(0.05)

    worker.stop()

    assert len(peaks) == 1
    assert peaks[0].capture_gain_db == pytest.approx(42.5)


def test_detection_worker_merges_nearby_peaks_before_tracking() -> None:
    input_queue: SampleQueue[SpectrumFrame] = SampleQueue(maxsize=8)
    merge_bandwidth_hz = 150_000.0
    worker = DetectionWorker(
        input_queue=input_queue,
        threshold_db=-40.0,
        min_distance_hz=0.0,
        merge_bandwidth_hz=merge_bandwidth_hz,
        confirm_hits=1,
    )
    worker.set_enabled(True)
    worker.start()

    fft_size = 1024
    center_hz = 100_000_000.0
    sample_rate_hz = 2_048_000.0
    floor_db = -80.0
    db_values = np.full(fft_size, floor_db, dtype=np.float64)
    for freq_hz, power_db in (
        (99_040_000.0, -28.0),
        (99_050_000.0, -18.0),
        (99_060_000.0, -24.0),
    ):
        bin_index = freq_to_bin(freq_hz, center_hz, sample_rate_hz, fft_size)
        db_values[bin_index] = power_db
    frame = SpectrumFrame(
        db_values=db_values,
        center_freq=center_hz,
        sample_rate=sample_rate_hz,
        timestamp=0.0,
    )

    raw_peaks = detect_peaks(frame, threshold_db=-40.0, min_distance_hz=0.0)
    assert len(raw_peaks) >= 2
    merged_peaks = merge_nearby_peaks(raw_peaks, merge_bandwidth_hz)
    assert len(merged_peaks) == 1

    input_queue.put_drop_oldest(frame)

    deadline = time.monotonic() + 2.0
    peaks = []
    while time.monotonic() < deadline:
        peaks = worker.state.snapshot()
        if peaks:
            break
        time.sleep(0.05)

    worker.stop()

    assert len(peaks) == 1
    assert peaks[0].frequency_hz == pytest.approx(99_050_000.0, rel=1e-4)
    assert peaks[0].power_db == pytest.approx(-18.0, abs=1.0)


def test_pipeline_detach_detection_stops_worker() -> None:
    device = MockSDRDevice(realtime=False)
    pipeline = Pipeline(device=device, fft_size=512)
    detection = pipeline.attach_detection()

    device.connect()
    pipeline.start()
    assert detection.is_running

    pipeline.detach_detection()
    assert pipeline.detection_worker is None
    assert not detection.is_running

    pipeline.stop()
    device.disconnect()
