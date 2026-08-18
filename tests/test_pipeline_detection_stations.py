"""Tests for station-name annotation in the detection worker."""

from __future__ import annotations

import time

from sdr_console.detect.station_db import StationDatabase
from sdr_console.dsp.axis import freq_to_bin
from sdr_console.dsp.frame import SpectrumFrame
from sdr_console.pipeline.detection_worker import DetectionWorker
from sdr_console.pipeline.sample_queue import SampleQueue

import numpy as np


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


def test_detection_worker_annotates_confirmed_peaks_with_station_names() -> None:
    input_queue: SampleQueue[SpectrumFrame] = SampleQueue(maxsize=8)
    station_db = StationDatabase([(100_050_000.0, "Mock FM")])
    worker = DetectionWorker(
        input_queue=input_queue,
        threshold_db=-40.0,
        window_frames=2,
        confirm_hits=1,
        station_db=station_db,
        station_match_tolerance_hz=5_000.0,
    )
    worker.set_enabled(True)
    worker.start()

    for timestamp in (0.0, 1.0):
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
    assert peaks[0].name == "Mock FM"


def test_reload_station_database_refreshes_names() -> None:
    input_queue: SampleQueue[SpectrumFrame] = SampleQueue(maxsize=4)
    worker = DetectionWorker(
        input_queue=input_queue,
        window_frames=1,
        confirm_hits=1,
        station_db=StationDatabase([]),
    )
    worker.set_enabled(True)
    worker.start()
    input_queue.put_drop_oldest(_synthetic_frame(99_900_000.0, timestamp=0.0))

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and not worker.state.snapshot():
        time.sleep(0.05)

    worker.set_station_db(StationDatabase([(99_900_000.0, "Renamed")]))
    worker._publish_confirmed_peaks()

    peaks = worker.state.snapshot()
    worker.stop()

    assert peaks[0].name == "Renamed"
