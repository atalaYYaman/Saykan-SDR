"""Unit tests for audio sinks (no sound card involved)."""

from __future__ import annotations

import numpy as np
import pytest

from sdr_console.audio.sink import NullAudioSink, sounddevice_available
from sdr_console.pipeline.sample_queue import SampleQueue


@pytest.fixture
def audio_queue() -> SampleQueue[np.ndarray]:
    return SampleQueue(maxsize=8)


def test_sink_joins_queued_blocks_into_fixed_frames(
    audio_queue: SampleQueue[np.ndarray],
) -> None:
    sink = NullAudioSink(48_000.0, audio_queue, volume=1.0)
    audio_queue.put_drop_oldest(np.arange(5, dtype=np.float32))
    audio_queue.put_drop_oldest(np.arange(5, 10, dtype=np.float32))

    first = sink.pull(4)
    second = sink.pull(4)

    np.testing.assert_allclose(first, [0.0, 1.0, 2.0, 3.0])
    np.testing.assert_allclose(second, [4.0, 5.0, 6.0, 7.0])
    assert sink.underruns == 0


def test_sink_keeps_the_remainder_of_a_partially_used_block(
    audio_queue: SampleQueue[np.ndarray],
) -> None:
    sink = NullAudioSink(48_000.0, audio_queue, volume=1.0)
    audio_queue.put_drop_oldest(np.arange(10, dtype=np.float32))

    sink.pull(3)
    rest = sink.pull(3)

    np.testing.assert_allclose(rest, [3.0, 4.0, 5.0])


def test_sink_pads_with_silence_and_counts_underruns(
    audio_queue: SampleQueue[np.ndarray],
) -> None:
    sink = NullAudioSink(48_000.0, audio_queue, volume=1.0)
    audio_queue.put_drop_oldest(np.ones(6, dtype=np.float32))

    played = sink.pull(4)
    starved = sink.pull(4)

    np.testing.assert_allclose(played, np.ones(4))
    np.testing.assert_allclose(starved, [1.0, 1.0, 0.0, 0.0])
    assert sink.underruns == 1


def test_sink_stays_silent_until_the_prefill_is_reached(
    audio_queue: SampleQueue[np.ndarray],
) -> None:
    sink = NullAudioSink(48_000.0, audio_queue, volume=1.0, prefill_s=100 / 48_000.0)
    audio_queue.put_drop_oldest(np.ones(40, dtype=np.float32))

    early = sink.pull(8)
    audio_queue.put_drop_oldest(np.ones(80, dtype=np.float32))
    late = sink.pull(8)

    # Buffering the first blocks is not a glitch, so it is not an underrun.
    np.testing.assert_allclose(early, np.zeros(8))
    np.testing.assert_allclose(late, np.ones(8))
    assert sink.underruns == 0


def test_sink_trims_the_buffer_to_bound_latency(
    audio_queue: SampleQueue[np.ndarray],
) -> None:
    rate_hz = 1_000.0
    sink = NullAudioSink(
        rate_hz,
        audio_queue,
        volume=1.0,
        prefill_s=0.01,
        max_latency_s=0.05,
    )
    for _ in range(6):
        audio_queue.put_drop_oldest(np.ones(20, dtype=np.float32))

    sink.pull(10)

    # Trimming drops whole blocks, so it stops at 40 rather than exactly 50.
    assert sink.trimmed_samples == 80
    assert sink.buffered_samples == 30


def test_sink_applies_volume(audio_queue: SampleQueue[np.ndarray]) -> None:
    sink = NullAudioSink(48_000.0, audio_queue, volume=0.25)
    audio_queue.put_drop_oldest(np.ones(4, dtype=np.float32))

    np.testing.assert_allclose(sink.pull(4), np.full(4, 0.25))


def test_sink_volume_is_clamped(audio_queue: SampleQueue[np.ndarray]) -> None:
    sink = NullAudioSink(48_000.0, audio_queue, volume=5.0)
    assert sink.volume == 1.0

    sink.volume = -2.0
    assert sink.volume == 0.0


def test_sink_rejects_a_non_positive_rate(audio_queue: SampleQueue[np.ndarray]) -> None:
    with pytest.raises(ValueError):
        NullAudioSink(0.0, audio_queue)


def test_null_sink_tracks_start_stop_and_history(
    audio_queue: SampleQueue[np.ndarray],
) -> None:
    sink = NullAudioSink(48_000.0, audio_queue, volume=1.0)
    assert not sink.is_running
    assert sink.played.size == 0

    sink.start()
    audio_queue.put_drop_oldest(np.ones(3, dtype=np.float32))
    sink.pull(2)
    sink.pull(2)
    sink.stop()

    assert not sink.is_running
    np.testing.assert_allclose(sink.played, [1.0, 1.0, 1.0, 0.0])


def test_sounddevice_available_reports_a_reason() -> None:
    available, detail = sounddevice_available()

    assert isinstance(available, bool)
    assert detail
