"""Orchestrates acquisition and processing worker threads."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

import numpy as np

from sdr_console.dsp.frame import SpectrumFrame
from sdr_console.pipeline.acquisition_worker import AcquisitionWorker
from sdr_console.pipeline.detection_worker import DetectionWorker
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
        self._detection_queue: SampleQueue[SpectrumFrame] | None = None
        self._detection_worker: DetectionWorker | None = None

    @property
    def output_queue(self) -> SampleQueue[SpectrumFrame]:
        return self._output_queue

    @property
    def detection_worker(self) -> DetectionWorker | None:
        return self._detection_worker

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

    def add_spectrum_consumer(self, maxsize: int = 8) -> SampleQueue[SpectrumFrame]:
        """Attach another queue that receives every processed spectrum frame."""
        spectrum_queue: SampleQueue[SpectrumFrame] = SampleQueue(maxsize=maxsize)
        self._processing.add_consumer(spectrum_queue)
        return spectrum_queue

    def remove_spectrum_consumer(self, spectrum_queue: SampleQueue[SpectrumFrame]) -> None:
        """Stop feeding a queue created by :meth:`add_spectrum_consumer`."""
        self._processing.remove_consumer(spectrum_queue)
        spectrum_queue.drain()

    def attach_detection(
        self,
        *,
        input_queue_maxsize: int = 8,
        **detection_kwargs,
    ) -> DetectionWorker:
        """Wire a detection worker to the spectrum output fan-out."""
        if self._detection_worker is not None:
            raise RuntimeError("detection worker already attached")

        detection_queue: SampleQueue[SpectrumFrame] = SampleQueue(maxsize=input_queue_maxsize)
        self._processing.add_consumer(detection_queue)
        self._detection_queue = detection_queue
        self._detection_worker = DetectionWorker(
            input_queue=detection_queue,
            device=self._device,
            **detection_kwargs,
        )
        if self.is_running:
            self._detection_worker.start()
        return self._detection_worker

    def detach_detection(self) -> None:
        """Stop and remove the optional detection worker."""
        if self._detection_worker is None:
            return

        self._detection_worker.stop()
        self._detection_worker = None

        if self._detection_queue is not None:
            self._processing.remove_consumer(self._detection_queue)
            self._detection_queue.drain()
            self._detection_queue = None

    @property
    def is_running(self) -> bool:
        detection_running = (
            self._detection_worker is not None and self._detection_worker.is_running
        )
        return self._acquisition.is_running or self._processing.is_running or detection_running

    @property
    def dropped_blocks(self) -> int:
        """Total blocks dropped from raw + output queues due to backpressure."""
        return self._raw_queue.dropped + self._output_queue.dropped

    def start(self) -> None:
        self._raw_queue.reset_dropped()
        self._output_queue.reset_dropped()
        self._processing.start()
        if self._detection_worker is not None:
            self._detection_worker.start()
        self._acquisition.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._acquisition.stop(timeout=timeout)
        if self._detection_worker is not None:
            self._detection_worker.stop(timeout=timeout)
        self._processing.stop(timeout=timeout)
        self.drain_raw()

    def drain_output(self) -> None:
        self._output_queue.drain()

    def drain_raw(self) -> None:
        self._raw_queue.drain()
