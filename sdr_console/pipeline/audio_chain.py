"""Wires the demodulation worker to an audio sink as one startable unit."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

import numpy as np

from sdr_console.audio.sink import DEFAULT_VOLUME, AudioSink, SoundDeviceAudioSink
from sdr_console.dsp.audio import DEFAULT_AUDIO_RATE_HZ
from sdr_console.dsp.channel import ChannelSpec
from sdr_console.pipeline.demod_worker import (
    DemodulatorFactory,
    DemodWorker,
    default_demodulator_factory,
)
from sdr_console.pipeline.sample_queue import SampleQueue

if TYPE_CHECKING:
    from sdr_console.hal.interface import SDRDeviceInterface

logger = logging.getLogger(__name__)

DEFAULT_AUDIO_QUEUE_MAXSIZE = 32
#: Builds a sink for a rate and queue; swapped out in tests.
SinkFactory = Callable[[float, SampleQueue[np.ndarray]], AudioSink]


def default_sink_factory(
    sample_rate_hz: float,
    audio_queue: SampleQueue[np.ndarray],
) -> AudioSink:
    return SoundDeviceAudioSink(sample_rate_hz=sample_rate_hz, audio_queue=audio_queue)


class AudioChain:
    """Listening path: raw IQ queue -> demodulator -> audio queue -> sound card.

    Owns the queue between the worker and the sink so the UI only has to start,
    stop and set the volume.
    """

    def __init__(
        self,
        device: SDRDeviceInterface,
        raw_queue: SampleQueue[np.ndarray],
        channel: ChannelSpec,
        preferred_audio_rate_hz: float = DEFAULT_AUDIO_RATE_HZ,
        volume: float = DEFAULT_VOLUME,
        demodulator_factory: DemodulatorFactory = default_demodulator_factory,
        sink_factory: SinkFactory = default_sink_factory,
        audio_queue_maxsize: int = DEFAULT_AUDIO_QUEUE_MAXSIZE,
    ) -> None:
        self._device = device
        self._volume = float(np.clip(volume, 0.0, 1.0))
        self._sink_factory = sink_factory
        self._audio_queue: SampleQueue[np.ndarray] = SampleQueue(
            maxsize=audio_queue_maxsize
        )
        self._sink: AudioSink | None = None
        self._worker = DemodWorker(
            device=device,
            raw_queue=raw_queue,
            audio_queue=self._audio_queue,
            channel=channel,
            preferred_audio_rate_hz=preferred_audio_rate_hz,
            demodulator_factory=demodulator_factory,
        )

    @property
    def worker(self) -> DemodWorker:
        return self._worker

    @property
    def sink(self) -> AudioSink | None:
        """Sink instance while running, ``None`` otherwise."""
        return self._sink

    @property
    def audio_queue(self) -> SampleQueue[np.ndarray]:
        return self._audio_queue

    @property
    def is_running(self) -> bool:
        return self._sink is not None and self._worker.is_running

    @property
    def volume(self) -> float:
        return self._volume

    @property
    def underruns(self) -> int:
        return self._sink.underruns if self._sink is not None else 0

    @property
    def dropped_blocks(self) -> int:
        return self._audio_queue.dropped

    def set_volume(self, volume: float) -> None:
        self._volume = float(np.clip(volume, 0.0, 1.0))
        if self._sink is not None:
            self._sink.volume = self._volume

    def set_channel(self, channel: ChannelSpec) -> None:
        """Retune the listening channel while playing."""
        self._worker.set_channel(channel)

    def set_demod_mode(self, mode: str) -> None:
        """Switch demodulation mode; applied at the next audio block."""
        from sdr_console.demod.factory import demodulator_factory

        self._worker.set_demodulator_factory(demodulator_factory(mode))

    def start(self) -> None:
        """Open the sound card, then start demodulating.

        Raises:
            AudioUnavailableError: When the sink cannot be opened; nothing is
                started in that case.
        """
        if self.is_running:
            return

        self._audio_queue.drain()
        self._audio_queue.reset_dropped()

        sink = self._sink_factory(self._worker.audio_rate_hz(), self._audio_queue)
        sink.volume = self._volume
        sink.start()
        self._sink = sink
        self._worker.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._worker.stop(timeout=timeout)
        if self._sink is not None:
            self._sink.stop()
            self._sink = None
        self._audio_queue.drain()
