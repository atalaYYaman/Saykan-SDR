"""Audio output sinks: where demodulated audio leaves the application."""

from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from collections import deque
from typing import Any, Protocol

import numpy as np

from sdr_console.audio.errors import AudioUnavailableError

logger = logging.getLogger(__name__)

DEFAULT_BLOCK_SIZE = 1024
DEFAULT_VOLUME = 0.5
#: Audio buffered before playback starts. Blocks arrive in bursts, so without a
#: cushion the card asks for samples that are only microseconds from arriving.
DEFAULT_PREFILL_S = 0.08
#: Upper bound on buffered audio; excess is dropped to keep latency in check.
DEFAULT_MAX_LATENCY_S = 0.3


class AudioBlockSource(Protocol):
    """Read side of whatever feeds a sink.

    Keeps this layer free of a dependency on the pipeline: a sink only needs to
    ask for the next block and be told when there is none.
    """

    def try_get(self, timeout: float | None = None) -> np.ndarray | None: ...


def sounddevice_available() -> tuple[bool, str]:
    """Report whether audio playback is possible.

    Returns:
        ``(available, detail)`` where detail names the output device or explains
        why playback is unavailable.
    """
    try:
        import sounddevice
    except ImportError:
        return False, "sounddevice is not installed (pip install sdr-console[audio])"

    try:
        info = sounddevice.query_devices(kind="output")
    except Exception as exc:
        return False, f"no output device: {exc}"

    name = str(info.get("name", "output device")) if isinstance(info, dict) else "output"
    return True, name


class AudioSink(ABC):
    """Consumes mono float32 blocks from a queue and plays them.

    The sink pulls rather than being pushed to: playback is driven by the sound
    card's own clock, so it takes exactly as many samples as it needs and fills
    the rest with silence when the producer falls behind.
    """

    @property
    @abstractmethod
    def sample_rate_hz(self) -> float:
        """Rate the output stream runs at, in Hz."""

    @property
    @abstractmethod
    def is_running(self) -> bool:
        """Whether the stream is open and playing."""

    @property
    @abstractmethod
    def volume(self) -> float:
        """Output gain in ``[0, 1]``."""

    @volume.setter
    @abstractmethod
    def volume(self, value: float) -> None: ...

    @property
    @abstractmethod
    def underruns(self) -> int:
        """Number of callbacks that had to insert silence."""

    @abstractmethod
    def start(self) -> None:
        """Open the output stream.

        Raises:
            AudioUnavailableError: When the backend or device is unusable.
        """

    @abstractmethod
    def stop(self) -> None:
        """Close the output stream. Safe to call when not running."""


class QueuePullSink(AudioSink):
    """Shared queue-draining logic: turns queued blocks into fixed-size frames.

    Keeps a small buffer of its own so bursty producers still sound continuous,
    and trims that buffer when it grows past ``max_latency_s`` so audio does not
    drift behind the display.
    """

    def __init__(
        self,
        sample_rate_hz: float,
        audio_queue: AudioBlockSource,
        volume: float = DEFAULT_VOLUME,
        prefill_s: float = DEFAULT_PREFILL_S,
        max_latency_s: float = DEFAULT_MAX_LATENCY_S,
    ) -> None:
        if sample_rate_hz <= 0.0:
            raise ValueError("sample_rate_hz must be positive")
        if prefill_s < 0.0:
            raise ValueError("prefill_s must not be negative")
        if max_latency_s < prefill_s:
            raise ValueError("max_latency_s must be at least prefill_s")

        self._sample_rate_hz = float(sample_rate_hz)
        self._queue = audio_queue
        self._volume = float(np.clip(volume, 0.0, 1.0))
        self._prefill_samples = int(prefill_s * self._sample_rate_hz)
        self._max_buffered = int(max_latency_s * self._sample_rate_hz)
        self._buffer: deque[np.ndarray] = deque()
        self._buffered = 0
        self._priming = True
        self._underruns = 0
        self._trimmed_samples = 0

    @property
    def sample_rate_hz(self) -> float:
        return self._sample_rate_hz

    @property
    def buffered_samples(self) -> int:
        """Audio held by the sink, i.e. its share of the output latency."""
        return self._buffered

    @property
    def trimmed_samples(self) -> int:
        """Samples discarded to stop the buffer from growing without bound."""
        return self._trimmed_samples

    @property
    def volume(self) -> float:
        return self._volume

    @volume.setter
    def volume(self, value: float) -> None:
        # Read by the callback thread; a single float store needs no lock.
        self._volume = float(np.clip(value, 0.0, 1.0))

    @property
    def underruns(self) -> int:
        return self._underruns

    def _absorb_queue(self) -> None:
        """Move everything the producer has queued into the local buffer."""
        while (block := self._queue.try_get()) is not None:
            if block.size == 0:
                continue
            self._buffer.append(np.asarray(block, dtype=np.float32))
            self._buffered += block.size

        while self._buffered > self._max_buffered and self._buffer:
            oldest = self._buffer.popleft()
            self._buffered -= oldest.size
            self._trimmed_samples += oldest.size

    def _take(self, frames: int) -> tuple[np.ndarray, int]:
        """Copy up to ``frames`` buffered samples into a fresh frame."""
        out = np.zeros(frames, dtype=np.float32)
        filled = 0
        while filled < frames and self._buffer:
            block = self._buffer[0]
            take = min(frames - filled, block.size)
            out[filled : filled + take] = block[:take]
            if take == block.size:
                self._buffer.popleft()
            else:
                self._buffer[0] = block[take:]
            self._buffered -= take
            filled += take
        return out, filled

    def _next_frames(self, frames: int) -> np.ndarray:
        """Pull ``frames`` samples, padding with silence when starved."""
        self._absorb_queue()

        if self._priming:
            if self._buffered < max(self._prefill_samples, frames):
                return np.zeros(frames, dtype=np.float32)
            self._priming = False

        out, filled = self._take(frames)
        if filled < frames:
            # Refill before playing again; dribbling out partial frames would
            # click on every callback instead of once.
            self._underruns += 1
            self._priming = True
        return out * self._volume


class NullAudioSink(QueuePullSink):
    """Test double: drains the queue on demand without touching hardware."""

    def __init__(
        self,
        sample_rate_hz: float,
        audio_queue: AudioBlockSource,
        volume: float = DEFAULT_VOLUME,
        prefill_s: float = 0.0,
        max_latency_s: float = DEFAULT_MAX_LATENCY_S,
    ) -> None:
        super().__init__(sample_rate_hz, audio_queue, volume, prefill_s, max_latency_s)
        self._running = False
        self._played: list[np.ndarray] = []

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def played(self) -> np.ndarray:
        """Everything handed out by :meth:`pull` so far."""
        if not self._played:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(self._played)

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def pull(self, frames: int) -> np.ndarray:
        """Stand in for the sound card asking for ``frames`` samples."""
        block = self._next_frames(frames)
        self._played.append(block)
        return block


class SoundDeviceAudioSink(QueuePullSink):
    """Plays audio through the system sound card via PortAudio.

    ``sounddevice`` is imported lazily so the console runs without the optional
    audio extra installed.
    """

    def __init__(
        self,
        sample_rate_hz: float,
        audio_queue: AudioBlockSource,
        volume: float = DEFAULT_VOLUME,
        block_size: int = DEFAULT_BLOCK_SIZE,
        device: int | str | None = None,
        prefill_s: float = DEFAULT_PREFILL_S,
        max_latency_s: float = DEFAULT_MAX_LATENCY_S,
    ) -> None:
        super().__init__(sample_rate_hz, audio_queue, volume, prefill_s, max_latency_s)
        self._block_size = max(0, block_size)
        self._device = device
        self._stream: Any | None = None
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._stream is not None

    def start(self) -> None:
        with self._lock:
            if self._stream is not None:
                return

            try:
                import sounddevice
            except ImportError as exc:
                raise AudioUnavailableError(
                    "sounddevice is not installed (pip install sdr-console[audio])"
                ) from exc

            try:
                stream = sounddevice.OutputStream(
                    samplerate=self._sample_rate_hz,
                    channels=1,
                    dtype="float32",
                    blocksize=self._block_size,
                    device=self._device,
                    callback=self._callback,
                )
                stream.start()
            except Exception as exc:
                raise AudioUnavailableError(f"cannot open audio output: {exc}") from exc

            self._stream = stream
            logger.info(
                "Audio output started at %.1f Hz (block %s)",
                self._sample_rate_hz,
                self._block_size,
            )

    def stop(self) -> None:
        with self._lock:
            stream = self._stream
            self._stream = None
        if stream is None:
            return
        try:
            stream.stop()
            stream.close()
        except Exception:
            logger.exception("Closing audio output failed")
        self._buffer.clear()
        self._buffered = 0
        self._priming = True

    def _callback(
        self,
        outdata: np.ndarray,
        frames: int,
        _time_info: Any,
        status: Any,
    ) -> None:
        # Runs on the PortAudio thread: never block, never raise.
        if status:
            logger.debug("Audio callback status: %s", status)
        try:
            outdata[:, 0] = self._next_frames(frames)
        except Exception:
            outdata.fill(0.0)
            logger.exception("Audio callback failed")
