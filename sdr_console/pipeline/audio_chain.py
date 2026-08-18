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
        demod_mode: str = "AM",
        deemphasis_tau_s: float = 75e-6,
        nfm_deemphasis: bool = False,
        afbw_hz: float | None = None,
        agc_enabled: bool | None = None,
        agc_preset: str | None = None,
        squelch_enabled: bool = False,
        squelch_threshold_db: float = -50.0,
        squelch_hysteresis_db: float = 3.0,
        squelch_hang_s: float = 0.15,
    ) -> None:
        self._device = device
        self._volume = float(np.clip(volume, 0.0, 1.0))
        self._sink_factory = sink_factory
        self._demod_mode = str(demod_mode)
        self._deemphasis_tau_s = float(deemphasis_tau_s)
        self._nfm_deemphasis = bool(nfm_deemphasis)
        self._afbw_hz = None if afbw_hz is None else float(afbw_hz)
        self._agc_enabled = None if agc_enabled is None else bool(agc_enabled)
        self._agc_preset = None if agc_preset is None else str(agc_preset)
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
            squelch_enabled=squelch_enabled,
            squelch_threshold_db=squelch_threshold_db,
            squelch_hysteresis_db=squelch_hysteresis_db,
            squelch_hang_s=squelch_hang_s,
        )

    def _factory_kwargs(self) -> dict:
        return {
            "deemphasis_tau_s": self._deemphasis_tau_s,
            "nfm_deemphasis": self._nfm_deemphasis,
            "afbw_hz": self._afbw_hz,
            "agc_enabled": self._agc_enabled,
            "agc_preset": self._agc_preset,
        }

    def _apply_factory(self) -> None:
        from sdr_console.demod.factory import demodulator_factory

        self._worker.set_demodulator_factory(
            demodulator_factory(self._demod_mode, **self._factory_kwargs())
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
        self._demod_mode = str(mode)
        self._apply_factory()

    def set_deemphasis(
        self,
        tau_s: float,
        *,
        nfm_deemphasis: bool | None = None,
    ) -> None:
        """Update FM de-emphasis; rebuilds the demodulator on the next block."""
        self._deemphasis_tau_s = float(tau_s)
        if nfm_deemphasis is not None:
            self._nfm_deemphasis = bool(nfm_deemphasis)
        self._apply_factory()

    def set_afbw(self, afbw_hz: float) -> None:
        """Update audio bandwidth; rebuilds the demodulator on the next block."""
        self._afbw_hz = float(afbw_hz)
        self._apply_factory()

    def set_agc(self, *, enabled: bool | None = None, preset: str | None = None) -> None:
        """Update AGC enable/preset; rebuilds the demodulator on the next block."""
        if enabled is not None:
            self._agc_enabled = bool(enabled)
        if preset is not None:
            self._agc_preset = str(preset)
        self._apply_factory()

    def set_squelch(
        self,
        *,
        enabled: bool | None = None,
        threshold_db: float | None = None,
        hysteresis_db: float | None = None,
        hang_s: float | None = None,
    ) -> None:
        """Update IF squelch; applied on the next audio block."""
        self._worker.set_squelch(
            enabled=enabled,
            threshold_db=threshold_db,
            hysteresis_db=hysteresis_db,
            hang_s=hang_s,
        )

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
