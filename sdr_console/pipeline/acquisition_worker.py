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
        self._raw_queue = raw_queue
        self._read_chunk_size = read_chunk_size
        self._on_error = on_error
        self._max_consecutive_errors = max(1, max_consecutive_errors)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

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
            self._raw_queue.put_drop_oldest(iq)
