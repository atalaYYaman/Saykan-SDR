"""Worker thread that acquires raw IQ from the HAL device."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

import numpy as np

from sdr_console.pipeline.sample_queue import SampleQueue

if TYPE_CHECKING:
    from sdr_console.hal.interface import SDRDeviceInterface

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONSECUTIVE_ERRORS = 5


class AcquisitionWorker:
    """Continuously reads IQ blocks from a device into a raw sample queue."""

    def __init__(
        self,
        device: SDRDeviceInterface,
        raw_queue: SampleQueue[np.ndarray],
        read_chunk_size: int,
        on_error: Callable[[str], None] | None = None,
        max_consecutive_errors: int = DEFAULT_MAX_CONSECUTIVE_ERRORS,
    ) -> None:
        self._device = device
        self._read_chunk_size = read_chunk_size
        self._on_error = on_error
        self._max_consecutive_errors = max(1, max_consecutive_errors)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        # Swapped as a whole so the reading thread never sees a partial list.
        self._consumers: tuple[SampleQueue[np.ndarray], ...] = (raw_queue,)
        self._consumers_lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def consumers(self) -> tuple[SampleQueue[np.ndarray], ...]:
        """Queues currently receiving every acquired block."""
        return self._consumers

    def add_consumer(self, raw_queue: SampleQueue[np.ndarray]) -> None:
        """Fan every acquired block out to ``raw_queue`` as well.

        Lets a second chain (demodulation) read the same raw IQ as the spectrum
        chain without either one waiting for the other.
        """
        with self._consumers_lock:
            if raw_queue in self._consumers:
                return
            self._consumers = (*self._consumers, raw_queue)

    def remove_consumer(self, raw_queue: SampleQueue[np.ndarray]) -> None:
        """Stop feeding ``raw_queue``."""
        with self._consumers_lock:
            self._consumers = tuple(q for q in self._consumers if q is not raw_queue)

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="AcquisitionWorker",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def _emit_error(self, message: str) -> None:
        logger.error("Acquisition fatal: %s", message)
        if self._on_error is not None:
            try:
                self._on_error(message)
            except Exception:
                logger.exception("on_error callback failed")

    def _run(self) -> None:
        consecutive_errors = 0
        while not self._stop_event.is_set():
            try:
                iq = self._device.read_samples(self._read_chunk_size)
            except RuntimeError as exc:
                message = str(exc) or "device not ready"
                logger.info("Acquisition stopped: %s", message)
                self._emit_error(message)
                break
            except Exception as exc:
                consecutive_errors += 1
                logger.exception(
                    "Acquisition read failed (%s/%s)",
                    consecutive_errors,
                    self._max_consecutive_errors,
                )
                if consecutive_errors >= self._max_consecutive_errors:
                    self._emit_error(
                        f"Acquisition failed after {consecutive_errors} errors: {exc}"
                    )
                    break
                continue

            consecutive_errors = 0
            # Every consumer gets the same array; blocks are treated as
            # read-only downstream so no copy is needed per chain.
            for consumer in self._consumers:
                consumer.put_drop_oldest(iq)
