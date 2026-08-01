"""Thread-safe bounded queue with drop-oldest backpressure."""

from __future__ import annotations

import queue
import threading
from typing import Generic, TypeVar

T = TypeVar("T")


class SampleQueue(Generic[T]):
    """Bounded queue that drops the oldest item when full."""

    def __init__(self, maxsize: int) -> None:
        if maxsize <= 0:
            raise ValueError("maxsize must be positive")
        self._queue: queue.Queue[T] = queue.Queue(maxsize=maxsize)
        self._dropped = 0
        self._drop_lock = threading.Lock()

    @property
    def maxsize(self) -> int:
        return self._queue.maxsize

    @property
    def dropped(self) -> int:
        """Number of items evicted because the queue was full."""
        with self._drop_lock:
            return self._dropped

    def qsize(self) -> int:
        return self._queue.qsize()

    def put_drop_oldest(self, item: T) -> None:
        """Enqueue ``item``, evicting the oldest entry if the queue is full."""
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            try:
                self._queue.get_nowait()
                with self._drop_lock:
                    self._dropped += 1
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(item)
            except queue.Full:
                pass

    def get(self, timeout: float | None = None) -> T:
        """Block until an item is available (or ``timeout`` elapses).

        Raises:
            queue.Empty: When ``timeout`` elapses with no item (kept for
                callers that intentionally use timed waits). Prefer
                ``try_get`` for non-raising polls.
        """
        if timeout is None:
            return self._queue.get()
        return self._queue.get(timeout=timeout)

    def try_get(self, timeout: float | None = None) -> T | None:
        """Return the next item, or ``None`` if empty / timed out."""
        try:
            if timeout is None:
                return self._queue.get_nowait()
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_nowait(self) -> T:
        return self._queue.get_nowait()

    def drain(self) -> None:
        """Remove and discard all queued items."""
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def reset_dropped(self) -> None:
        with self._drop_lock:
            self._dropped = 0
