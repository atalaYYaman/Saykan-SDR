"""Common contract for every demodulation mode."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

import numpy as np

from sdr_console.dsp.channelizer import ChannelizedBlock


class Demodulator(ABC):
    """Turns baseband channel blocks into mono audio.

    Implementations are stateful: they keep filter and phase state so that
    consecutive blocks join without clicks. They know nothing about hardware,
    queues or Qt — a worker thread feeds them blocks and forwards the audio.

    Adding a mode means adding a subclass; existing modes never change.
    """

    #: Short label used by the UI and config, e.g. ``AM``.
    MODE: ClassVar[str]
    #: Channel bandwidth this mode expects when the user picks it.
    DEFAULT_BANDWIDTH_HZ: ClassVar[float]

    @property
    def mode(self) -> str:
        """Mode label of this instance."""
        return type(self).MODE

    @property
    @abstractmethod
    def input_rate_hz(self) -> float:
        """Baseband rate this instance was built for, in Hz."""

    @property
    @abstractmethod
    def audio_rate_hz(self) -> float:
        """Rate of the audio returned by :meth:`process`, in Hz."""

    @abstractmethod
    def reset(self) -> None:
        """Drop all carried-over state (call when tuning or mode changes)."""

    @abstractmethod
    def process(self, block: ChannelizedBlock) -> np.ndarray:
        """Demodulate one baseband block.

        Args:
            block: Channel samples at :attr:`input_rate_hz`.

        Returns:
            Mono float32 audio in ``[-1, 1]`` at :attr:`audio_rate_hz`.

        Raises:
            ValueError: When ``block.sample_rate_hz`` does not match
                :attr:`input_rate_hz`.
        """
