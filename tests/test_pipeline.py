"""Unit tests for pipeline queues and workers."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np
import pytest

from sdr_console.dsp.frame import SpectrumFrame
from sdr_console.hal.file_device import FileIQDevice
from sdr_console.hal.mock_device import DEFAULT_CENTER_FREQ_HZ, MockSDRDevice, MockTone
from sdr_console.pipeline.pipeline import Pipeline
from sdr_console.pipeline.sample_queue import SampleQueue


def test_sample_queue_rejects_non_positive_maxsize() -> None:
    with pytest.raises(ValueError):
        SampleQueue(maxsize=0)


def test_sample_queue_drop_oldest_evicts_first_item() -> None:
    sample_queue: SampleQueue[int] = SampleQueue(maxsize=2)

    sample_queue.put_drop_oldest(1)
    sample_queue.put_drop_oldest(2)
    sample_queue.put_drop_oldest(3)

    assert sample_queue.qsize() == 2
    assert sample_queue.get_nowait() == 2
    assert sample_queue.get_nowait() == 3


def test_sample_queue_drain_clears_all_items() -> None:
    sample_queue: SampleQueue[int] = SampleQueue(maxsize=4)
    sample_queue.put_drop_oldest(10)
    sample_queue.put_drop_oldest(20)

    sample_queue.drain()

    assert sample_queue.qsize() == 0
    assert sample_queue.try_get() is None


def test_sample_queue_try_get_returns_none_when_empty() -> None:
    sample_queue: SampleQueue[int] = SampleQueue(maxsize=1)
    assert sample_queue.try_get() is None


def test_pipeline_produces_spectrum_frames_end_to_end(fixtures_dir: Path) -> None:
    fixture = fixtures_dir / "single_tone.npy"
    if not fixture.exists():
        from tests.fixtures.generate import generate_all

        generate_all()

    fft_size = 1024
    device = FileIQDevice(
        fixture,
        sample_rate_hz=2_048_000.0,
        center_freq_hz=DEFAULT_CENTER_FREQ_HZ,
        gain_db=50.0,
    )
    pipeline = Pipeline(device=device, fft_size=fft_size, raw_queue_maxsize=4)

    device.connect()
    pipeline.start()

    frame: SpectrumFrame | None = None
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        frame = pipeline.output_queue.try_get(timeout=0.1)
        if frame is not None:
            break

    pipeline.stop()
    device.disconnect()

    assert frame is not None
    assert frame.db_values.shape == (fft_size,)
    assert frame.center_freq == device.center_freq_hz
    assert frame.sample_rate == device.sample_rate_hz
    assert int(np.argmax(frame.db_values)) > fft_size // 2


def test_pipeline_stop_joins_workers() -> None:
    device = MockSDRDevice(realtime=False)
    pipeline = Pipeline(device=device, fft_size=512)

    device.connect()
    pipeline.start()
    assert pipeline.is_running

    pipeline.stop()
    device.disconnect()

    assert not pipeline.is_running


def test_processing_worker_survives_dsp_errors(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from sdr_console.pipeline import processing_worker as pw_module

    def boom(*_args, **_kwargs):
        raise RuntimeError("forced DSP failure")

    monkeypatch.setattr(pw_module, "compute_spectrum_frame", boom)

    device = MockSDRDevice(
        tones=(MockTone(DEFAULT_CENTER_FREQ_HZ + 50_000.0, 1.0),),
        noise_amplitude=0.0,
        realtime=False,
    )
    pipeline = Pipeline(device=device, fft_size=256, raw_queue_maxsize=4)

    with caplog.at_level(logging.ERROR):
        device.connect()
        pipeline.start()
        time.sleep(0.3)
        assert pipeline.is_running
        pipeline.stop()
        device.disconnect()

    assert any("DSP processing failed" in record.message for record in caplog.records)
