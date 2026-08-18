"""Worker thread that converts raw IQ blocks into spectrum frames."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

import numpy as np

from sdr_console.dsp.frame import SpectrumFrame
from sdr_console.dsp.spectrum import compute_spectrum_frame
from sdr_console.pipeline.sample_queue import SampleQueue

if TYPE_CHECKING:
    from sdr_console.hal.interface import SDRDeviceInterface

logger = logging.getLogger(__name__)


class ProcessingWorker:
    """Reads raw IQ, runs DSP, and publishes ``SpectrumFrame`` rows."""

    def __init__(
        self,
        device: SDRDeviceInterface,
        raw_queue: SampleQueue[np.ndarray],
        output_queue: SampleQueue[SpectrumFrame],
        fft_size: int,
        poll_timeout_s: float = 0.1,
    ) -> None:
        self._device = device
        self._raw_queue = raw_queue
        self._output_queue = output_queue
        self._fft_size = fft_size
        self._poll_timeout_s = poll_timeout_s
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._consumers_lock = threading.Lock()
        self._output_queues: tuple[SampleQueue[SpectrumFrame], ...] = (output_queue,)

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def output_queues(self) -> tuple[SampleQueue[SpectrumFrame], ...]:
        """Queues currently receiving every processed spectrum frame."""
        return self._output_queues

    def add_consumer(self, output_queue: SampleQueue[SpectrumFrame]) -> None:
        """Fan every spectrum frame out to ``output_queue`` as well."""
        with self._consumers_lock:
            if output_queue in self._output_queues:
                return
            self._output_queues = (*self._output_queues, output_queue)

    def remove_consumer(self, output_queue: SampleQueue[SpectrumFrame]) -> None:
        """Stop feeding ``output_queue``."""
        with self._consumers_lock:
            self._output_queues = tuple(q for q in self._output_queues if q is not output_queue)

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="ProcessingWorker",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def _run(self) -> None:
        while not self._stop_event.is_set():
            iq = self._raw_queue.try_get(timeout=self._poll_timeout_s)
            if iq is None:
                continue

            try:
                frame = compute_spectrum_frame(
                    iq,
                    fft_size=self._fft_size,
                    center_freq=self._device.center_freq_hz,
                    sample_rate=self._device.sample_rate_hz,
                )
            except Exception:
                logger.exception("DSP processing failed; continuing")
                continue

            for consumer in self._output_queues:
                consumer.put_drop_oldest(frame)
