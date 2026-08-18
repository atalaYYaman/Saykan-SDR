"""Tests for the parallel demodulation chain and its audio plumbing."""

from __future__ import annotations

import time

import numpy as np
import pytest

from sdr_console.audio.sink import AudioSink, NullAudioSink
from sdr_console.dsp.channel import ChannelSpec
from sdr_console.hal.mock_device import MockSDRDevice
from sdr_console.hal.scenarios import AMMockDevice, am_tone
from sdr_console.pipeline.acquisition_worker import AcquisitionWorker
from sdr_console.pipeline.audio_chain import AudioChain
from sdr_console.pipeline.demod_worker import DemodWorker
from sdr_console.pipeline.pipeline import Pipeline
from sdr_console.pipeline.sample_queue import SampleQueue

CENTER_HZ = 100_000_000.0
SAMPLE_RATE_HZ = 2_048_000.0
CARRIER_OFFSET_HZ = 50_000.0
AUDIO_FREQ_HZ = 1_000.0
READ_SIZE = 16_384
AUDIO_RATE_HZ = 48_000.0


def dominant_frequency_hz(audio: np.ndarray, audio_rate_hz: float) -> float:
    spectrum = np.abs(np.fft.rfft(audio * np.hanning(audio.size)))
    freqs = np.fft.rfftfreq(audio.size, d=1.0 / audio_rate_hz)
    spectrum[freqs < 20.0] = 0.0
    return float(freqs[int(np.argmax(spectrum))])


def wait_until(predicate, timeout_s: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


@pytest.fixture
def am_device() -> AMMockDevice:
    device = am_tone(
        offset_hz=CARRIER_OFFSET_HZ,
        audio_freq_hz=AUDIO_FREQ_HZ,
        center_freq_hz=CENTER_HZ,
        sample_rate_hz=SAMPLE_RATE_HZ,
    )
    device.connect()
    return device


@pytest.fixture
def channel() -> ChannelSpec:
    return ChannelSpec(CENTER_HZ + CARRIER_OFFSET_HZ, 10_000.0)


def feed(device: AMMockDevice, raw_queue: SampleQueue[np.ndarray], blocks: int) -> None:
    for _ in range(blocks):
        raw_queue.put_drop_oldest(device.read_samples(READ_SIZE))


def test_acquisition_fans_blocks_out_to_every_consumer() -> None:
    device = MockSDRDevice(realtime=False)
    first: SampleQueue[np.ndarray] = SampleQueue(maxsize=64)
    second: SampleQueue[np.ndarray] = SampleQueue(maxsize=64)
    worker = AcquisitionWorker(device, first, read_chunk_size=1024)
    worker.add_consumer(second)

    device.connect()
    worker.start()
    got_both = wait_until(lambda: first.qsize() > 0 and second.qsize() > 0)
    worker.stop()
    device.disconnect()

    assert got_both
    assert worker.consumers == (first, second)


def test_acquisition_stops_feeding_a_removed_consumer() -> None:
    device = MockSDRDevice(realtime=False)
    first: SampleQueue[np.ndarray] = SampleQueue(maxsize=64)
    second: SampleQueue[np.ndarray] = SampleQueue(maxsize=64)
    worker = AcquisitionWorker(device, first, read_chunk_size=1024)
    worker.add_consumer(second)
    worker.add_consumer(second)  # adding twice must not duplicate

    assert worker.consumers == (first, second)

    worker.remove_consumer(second)
    device.connect()
    worker.start()
    wait_until(lambda: first.qsize() > 0)
    worker.stop()
    device.disconnect()

    assert worker.consumers == (first,)
    assert second.qsize() == 0


def test_pipeline_raw_consumer_can_be_added_and_removed() -> None:
    device = MockSDRDevice(realtime=False)
    pipeline = Pipeline(device=device, fft_size=512, read_chunk_size=1024)
    extra = pipeline.add_raw_consumer(maxsize=32)

    device.connect()
    pipeline.start()
    received = wait_until(lambda: extra.qsize() > 0)
    pipeline.remove_raw_consumer(extra)
    time.sleep(0.05)
    after_removal = extra.qsize()
    pipeline.stop()
    device.disconnect()

    assert received
    assert after_removal == 0


def test_demod_worker_produces_the_modulating_tone(
    am_device: AMMockDevice,
    channel: ChannelSpec,
) -> None:
    raw_queue: SampleQueue[np.ndarray] = SampleQueue(maxsize=64)
    audio_queue: SampleQueue[np.ndarray] = SampleQueue(maxsize=64)
    worker = DemodWorker(
        device=am_device,
        raw_queue=raw_queue,
        audio_queue=audio_queue,
        channel=channel,
        preferred_audio_rate_hz=AUDIO_RATE_HZ,
    )

    feed(am_device, raw_queue, blocks=8)
    worker.start()
    drained = wait_until(lambda: raw_queue.qsize() == 0 and audio_queue.qsize() >= 6)
    worker.stop()

    chunks = []
    while (block := audio_queue.try_get()) is not None:
        chunks.append(block)
    audio = np.concatenate(chunks)

    assert drained
    assert worker.plan is not None
    assert worker.demodulator is not None
    assert worker.demodulator.mode == "AM"
    assert audio.dtype == np.float32
    assert dominant_frequency_hz(
        audio[audio.size // 4 :], worker.demodulator.audio_rate_hz
    ) == pytest.approx(AUDIO_FREQ_HZ, rel=0.05)


def test_demod_worker_squelch_mutes_when_channel_is_below_threshold(
    am_device: AMMockDevice,
    channel: ChannelSpec,
) -> None:
    raw_queue: SampleQueue[np.ndarray] = SampleQueue(maxsize=64)
    audio_queue: SampleQueue[np.ndarray] = SampleQueue(maxsize=64)
    worker = DemodWorker(
        device=am_device,
        raw_queue=raw_queue,
        audio_queue=audio_queue,
        channel=channel,
        preferred_audio_rate_hz=AUDIO_RATE_HZ,
        squelch_enabled=True,
        # Unit-amplitude IF sits near 0 dBFS; this threshold never opens.
        squelch_threshold_db=20.0,
        squelch_hang_s=0.0,
    )

    feed(am_device, raw_queue, blocks=6)
    worker.start()
    drained = wait_until(lambda: raw_queue.qsize() == 0 and audio_queue.qsize() >= 4)
    worker.stop()

    chunks = []
    while (block := audio_queue.try_get()) is not None:
        chunks.append(block)
    audio = np.concatenate(chunks)

    assert drained
    assert float(np.max(np.abs(audio))) == pytest.approx(0.0)


def test_demod_worker_squelch_opens_for_a_strong_channel(
    am_device: AMMockDevice,
    channel: ChannelSpec,
) -> None:
    raw_queue: SampleQueue[np.ndarray] = SampleQueue(maxsize=64)
    audio_queue: SampleQueue[np.ndarray] = SampleQueue(maxsize=64)
    worker = DemodWorker(
        device=am_device,
        raw_queue=raw_queue,
        audio_queue=audio_queue,
        channel=channel,
        preferred_audio_rate_hz=AUDIO_RATE_HZ,
        squelch_enabled=True,
        squelch_threshold_db=-80.0,
        squelch_hang_s=0.0,
    )

    feed(am_device, raw_queue, blocks=8)
    worker.start()
    drained = wait_until(lambda: raw_queue.qsize() == 0 and audio_queue.qsize() >= 6)
    worker.stop()

    chunks = []
    while (block := audio_queue.try_get()) is not None:
        chunks.append(block)
    audio = np.concatenate(chunks)

    assert drained
    assert float(np.max(np.abs(audio))) > 0.05
    assert dominant_frequency_hz(
        audio[audio.size // 4 :], worker.demodulator.audio_rate_hz
    ) == pytest.approx(AUDIO_FREQ_HZ, rel=0.05)


def test_demod_worker_audio_rate_is_independent_of_bandwidth(
    am_device: AMMockDevice,
    channel: ChannelSpec,
) -> None:
    worker = DemodWorker(
        device=am_device,
        raw_queue=SampleQueue(maxsize=4),
        audio_queue=SampleQueue(maxsize=4),
        channel=channel,
        preferred_audio_rate_hz=AUDIO_RATE_HZ,
    )

    narrow = worker.audio_rate_hz(bandwidth_hz=10_000.0)
    wide = worker.audio_rate_hz(bandwidth_hz=350_000.0)

    # Bandwidth changes must not force the audio stream to be reopened.
    assert narrow == pytest.approx(wide)


def test_demod_worker_replans_when_bandwidth_changes(
    am_device: AMMockDevice,
    channel: ChannelSpec,
) -> None:
    raw_queue: SampleQueue[np.ndarray] = SampleQueue(maxsize=64)
    audio_queue: SampleQueue[np.ndarray] = SampleQueue(maxsize=64)
    worker = DemodWorker(
        device=am_device,
        raw_queue=raw_queue,
        audio_queue=audio_queue,
        channel=channel,
        preferred_audio_rate_hz=AUDIO_RATE_HZ,
    )

    feed(am_device, raw_queue, blocks=2)
    worker.start()
    wait_until(lambda: worker.plan is not None)
    narrow_decimation = worker.plan.channel.decimation if worker.plan else 0

    worker.set_channel(channel.with_bandwidth(350_000.0))
    feed(am_device, raw_queue, blocks=2)
    replanned = wait_until(
        lambda: worker.plan is not None
        and worker.plan.channel.decimation != narrow_decimation
    )
    audio_rate = worker.demodulator.audio_rate_hz if worker.demodulator else 0.0
    worker.stop()

    assert replanned
    assert audio_rate == pytest.approx(worker.audio_rate_hz())


def test_demod_worker_survives_demodulation_errors(
    am_device: AMMockDevice,
    channel: ChannelSpec,
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw_queue: SampleQueue[np.ndarray] = SampleQueue(maxsize=8)
    audio_queue: SampleQueue[np.ndarray] = SampleQueue(maxsize=8)

    def broken_factory(input_rate_hz: float, audio_decimation: int):
        raise RuntimeError("forced demod failure")

    worker = DemodWorker(
        device=am_device,
        raw_queue=raw_queue,
        audio_queue=audio_queue,
        channel=channel,
        preferred_audio_rate_hz=AUDIO_RATE_HZ,
        demodulator_factory=broken_factory,
    )

    feed(am_device, raw_queue, blocks=2)
    worker.start()
    logged = wait_until(
        lambda: any("Demodulation failed" in r.message for r in caplog.records)
    )
    still_running = worker.is_running
    worker.stop()

    assert logged
    assert still_running
    assert audio_queue.qsize() == 0


def test_audio_chain_plays_the_demodulated_tone(
    am_device: AMMockDevice,
    channel: ChannelSpec,
) -> None:
    raw_queue: SampleQueue[np.ndarray] = SampleQueue(maxsize=64)
    sinks: list[NullAudioSink] = []

    def sink_factory(rate_hz: float, queue: SampleQueue[np.ndarray]) -> AudioSink:
        sink = NullAudioSink(rate_hz, queue)
        sinks.append(sink)
        return sink

    chain = AudioChain(
        device=am_device,
        raw_queue=raw_queue,
        channel=channel,
        preferred_audio_rate_hz=AUDIO_RATE_HZ,
        volume=1.0,
        sink_factory=sink_factory,
    )

    feed(am_device, raw_queue, blocks=8)
    chain.start()
    assert chain.is_running
    filled = wait_until(lambda: chain.audio_queue.qsize() >= 6)

    sink = sinks[0]
    frames = 1024
    for _ in range(4):
        sink.pull(frames)
    chain.stop()

    assert filled
    assert not chain.is_running
    assert sink.sample_rate_hz == pytest.approx(chain.worker.audio_rate_hz())
    assert dominant_frequency_hz(sink.played, sink.sample_rate_hz) == pytest.approx(
        AUDIO_FREQ_HZ, rel=0.05
    )


def test_audio_chain_volume_reaches_the_sink(
    am_device: AMMockDevice,
    channel: ChannelSpec,
) -> None:
    sinks: list[NullAudioSink] = []

    def sink_factory(rate_hz: float, queue: SampleQueue[np.ndarray]) -> AudioSink:
        sink = NullAudioSink(rate_hz, queue)
        sinks.append(sink)
        return sink

    chain = AudioChain(
        device=am_device,
        raw_queue=SampleQueue(maxsize=8),
        channel=channel,
        volume=0.3,
        sink_factory=sink_factory,
    )
    chain.start()
    chain.set_volume(0.8)
    volume_while_running = sinks[0].volume
    chain.stop()

    chain.set_volume(0.1)

    assert volume_while_running == pytest.approx(0.8)
    assert chain.volume == pytest.approx(0.1)
