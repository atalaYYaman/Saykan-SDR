"""Orchestrates acquisition and processing worker threads."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

import numpy as np

from sdr_console.dsp.frame import SpectrumFrame
from sdr_console.pipeline.acquisition_worker import AcquisitionWorker
from sdr_console.pipeline.processing_worker import ProcessingWorker
from sdr_console.pipeline.sample_queue import SampleQueue

if TYPE_CHECKING:
    from sdr_console.hal.interface import SDRDeviceInterface

logger = logging.getLogger(__name__)


class Pipeline:
    """Two-stage threaded pipeline: device IQ -> DSP -> UI queue."""

    def __init__(
        self,
        device: SDRDeviceInterface,
        fft_size: int,
        read_chunk_size: int | None = None,
        raw_queue_maxsize: int = 8,
        output_queue: SampleQueue[SpectrumFrame] | None = None,
        output_queue_maxsize: int = 32,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        self._device = device
        self._fft_size = fft_size
        self._read_chunk_size = read_chunk_size or fft_size
        self._on_error = on_error

        if self._read_chunk_size < fft_size:
            logger.warning(
                "read_chunk_size (%s) < fft_size (%s); DSP will zero-pad",
                self._read_chunk_size,
                fft_size,
            )

        self._raw_queue: SampleQueue[np.ndarray] = SampleQueue(maxsize=raw_queue_maxsize)
        self._output_queue = output_queue or SampleQueue(maxsize=output_queue_maxsize)

        self._acquisition = AcquisitionWorker(
            device=device,
            raw_queue=self._raw_queue,
            read_chunk_size=self._read_chunk_size,
            on_error=on_error,
        )
        self._processing = ProcessingWorker(
            device=device,
            raw_queue=self._raw_queue,
            output_queue=self._output_queue,
            fft_size=fft_size,
        )

    @property
    def output_queue(self) -> SampleQueue[SpectrumFrame]:
        return self._output_queue

    @property
    def read_chunk_size(self) -> int:
        return self._read_chunk_size

    def add_raw_consumer(self, maxsize: int = 8) -> SampleQueue[np.ndarray]:
        """Create a queue that also receives every acquired IQ block.

        Used to run a second chain (demodulation) on the same samples; it can be
        added and removed while the pipeline is running.
        """
        raw_queue: SampleQueue[np.ndarray] = SampleQueue(maxsize=maxsize)
        self._acquisition.add_consumer(raw_queue)
        return raw_queue

    def remove_raw_consumer(self, raw_queue: SampleQueue[np.ndarray]) -> None:
        """Stop feeding a queue created by :meth:`add_raw_consumer`."""
        self._acquisition.remove_consumer(raw_queue)
        raw_queue.drain()

    @property
    def is_running(self) -> bool:
        return self._acquisition.is_running or self._processing.is_running

    @property
    def dropped_blocks(self) -> int:
        """Total blocks dropped from raw + output queues due to backpressure."""
        return self._raw_queue.dropped + self._output_queue.dropped

    def start(self) -> None:
        self._raw_queue.reset_dropped()
        self._output_queue.reset_dropped()
        self._processing.start()
        self._acquisition.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._acquisition.stop(timeout=timeout)
        self._processing.stop(timeout=timeout)
        self.drain_raw()

    def drain_output(self) -> None:
        self._output_queue.drain()

    def drain_raw(self) -> None:
        self._raw_queue.drain()
