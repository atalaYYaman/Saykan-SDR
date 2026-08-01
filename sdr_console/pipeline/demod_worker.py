"""Worker thread that turns raw IQ into audio, parallel to the spectrum chain."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

import numpy as np

from sdr_console.demod.am import AMDemodulator
from sdr_console.demod.base import Demodulator
from sdr_console.dsp.audio import DemodChainPlan, plan_demod_chain
from sdr_console.dsp.channel import ChannelSpec
from sdr_console.dsp.channelizer import ChannelizerState, channelize
from sdr_console.pipeline.sample_queue import SampleQueue

if TYPE_CHECKING:
    from sdr_console.hal.interface import SDRDeviceInterface

logger = logging.getLogger(__name__)

#: Builds a demodulator for an IF rate and a forced audio decimation factor.
DemodulatorFactory = Callable[[float, int], Demodulator]


def default_demodulator_factory(
    input_rate_hz: float,
    audio_decimation: int,
) -> Demodulator:
    return AMDemodulator(
        input_rate_hz=input_rate_hz,
        audio_decimation=audio_decimation,
    )


class DemodWorker:
    """Second chain on the same raw IQ: channel filter, demodulate, enqueue audio.

    Runs independently of the spectrum chain — it has its own raw queue, so
    neither chain waits for the other and audio keeps flowing while the display
    drops frames (or the reverse).
    """

    def __init__(
        self,
        device: SDRDeviceInterface,
        raw_queue: SampleQueue[np.ndarray],
        audio_queue: SampleQueue[np.ndarray],
        channel: ChannelSpec,
        preferred_audio_rate_hz: float,
        demodulator_factory: DemodulatorFactory = default_demodulator_factory,
        poll_timeout_s: float = 0.1,
    ) -> None:
        self._device = device
        self._raw_queue = raw_queue
        self._audio_queue = audio_queue
        self._preferred_audio_rate_hz = preferred_audio_rate_hz
        self._factory = demodulator_factory
        self._poll_timeout_s = poll_timeout_s

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        self._settings_lock = threading.Lock()
        self._channel = channel
        self._factory_changed = False

        self._plan: DemodChainPlan | None = None
        self._plan_key: tuple[float, float] | None = None
        self._demodulator: Demodulator | None = None
        self._channelizer_state: ChannelizerState | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def channel(self) -> ChannelSpec:
        return self._channel

    @property
    def demodulator(self) -> Demodulator | None:
        """Current demodulator, or ``None`` before the first block."""
        return self._demodulator

    @property
    def plan(self) -> DemodChainPlan | None:
        """Current decimation plan, or ``None`` before the first block."""
        return self._plan

    def audio_rate_hz(self, bandwidth_hz: float | None = None) -> float:
        """Audio rate this worker will produce, without running it.

        The rate depends only on the device sample rate, so callers can open the
        audio stream before the first block arrives.
        """
        bandwidth = self._channel.bandwidth_hz if bandwidth_hz is None else bandwidth_hz
        plan = plan_demod_chain(
            self._device.sample_rate_hz,
            bandwidth,
            self._preferred_audio_rate_hz,
        )
        return plan.audio_rate_hz

    def set_channel(self, channel: ChannelSpec) -> None:
        """Retune or re-filter; applied at the next block boundary."""
        with self._settings_lock:
            self._channel = channel

    def set_demodulator_factory(self, factory: DemodulatorFactory) -> None:
        """Switch mode; the new demodulator is built at the next block."""
        with self._settings_lock:
            self._factory = factory
            self._factory_changed = True

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="DemodWorker",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def _rebuild(self, sample_rate_hz: float, bandwidth_hz: float) -> None:
        """Re-plan the chain and start a fresh demodulator."""
        with self._settings_lock:
            factory = self._factory
            self._factory_changed = False

        self._plan = plan_demod_chain(
            sample_rate_hz,
            bandwidth_hz,
            self._preferred_audio_rate_hz,
        )
        self._plan_key = (sample_rate_hz, bandwidth_hz)
        self._demodulator = factory(self._plan.if_rate_hz, self._plan.audio_decimation)
        self._channelizer_state = None
        logger.info(
            "Demod chain: %s, IF %.1f Hz (dec %s), audio %.1f Hz (dec %s)",
            self._demodulator.mode,
            self._plan.if_rate_hz,
            self._plan.channel.decimation,
            self._plan.audio_rate_hz,
            self._plan.audio_decimation,
        )

    def _run(self) -> None:
        while not self._stop_event.is_set():
            iq = self._raw_queue.try_get(timeout=self._poll_timeout_s)
            if iq is None:
                continue

            with self._settings_lock:
                channel = self._channel
                factory_changed = self._factory_changed
            sample_rate_hz = self._device.sample_rate_hz

            try:
                if factory_changed or self._plan_key != (
                    sample_rate_hz,
                    channel.bandwidth_hz,
                ):
                    self._rebuild(sample_rate_hz, channel.bandwidth_hz)

                plan = self._plan
                demodulator = self._demodulator
                if plan is None or demodulator is None:
                    continue

                block, self._channelizer_state = channelize(
                    iq,
                    channel,
                    self._device.center_freq_hz,
                    sample_rate_hz,
                    plan.channel,
                    state=self._channelizer_state,
                )
                audio = demodulator.process(block)
            except Exception:
                logger.exception("Demodulation failed; continuing")
                self._channelizer_state = None
                continue

            if audio.size:
                self._audio_queue.put_drop_oldest(audio)
