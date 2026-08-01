"""Frequency modulation: phase discriminator."""

from __future__ import annotations

from typing import ClassVar

import numpy as np

from sdr_console.demod.base import Demodulator
from sdr_console.dsp.audio import (
    DEFAULT_AUDIO_RATE_HZ,
    DEFAULT_DC_CUTOFF_HZ,
    apply_iir,
    clip_audio,
    design_dc_blocker,
    plan_audio_decimation,
)
from sdr_console.dsp.channelizer import ChannelizedBlock, filter_and_decimate


class FMDemodulator(Demodulator):
    """FM via ``angle(x[n] * conj(x[n-1]))``, then DC removal and decimation.

    Subclasses only set :attr:`MODE` and :attr:`DEFAULT_BANDWIDTH_HZ`; the
    discriminator itself is identical for narrow and wide FM. Bandwidth is chosen
    upstream in the channel filter.
    """

    MODE: ClassVar[str]
    DEFAULT_BANDWIDTH_HZ: ClassVar[float]

    def __init__(
        self,
        input_rate_hz: float,
        preferred_audio_rate_hz: float = DEFAULT_AUDIO_RATE_HZ,
        dc_cutoff_hz: float = DEFAULT_DC_CUTOFF_HZ,
        gain: float | None = None,
        audio_decimation: int | None = None,
    ) -> None:
        if input_rate_hz <= 0.0:
            raise ValueError("input_rate_hz must be positive")

        self._input_rate_hz = float(input_rate_hz)
        self._gain = (
            float(input_rate_hz / (2.0 * np.pi))
            if gain is None
            else float(gain)
        )
        if self._gain <= 0.0:
            raise ValueError("gain must be positive")

        self._plan = plan_audio_decimation(
            self._input_rate_hz,
            preferred_audio_rate_hz,
            decimation=audio_decimation,
        )
        self._dc_b, self._dc_a = design_dc_blocker(self._input_rate_hz, dc_cutoff_hz)

        self._prev_sample = 0.0 + 0.0j
        self._dc_state: np.ndarray | None = None
        self._audio_state: np.ndarray | None = None
        self._audio_offset = 0

    @property
    def input_rate_hz(self) -> float:
        return self._input_rate_hz

    @property
    def audio_rate_hz(self) -> float:
        return self._plan.audio_rate_hz

    @property
    def decimation(self) -> int:
        return self._plan.decimation

    def reset(self) -> None:
        self._prev_sample = 0.0 + 0.0j
        self._dc_state = None
        self._audio_state = None
        self._audio_offset = 0

    def _discriminate(self, samples: np.ndarray) -> np.ndarray:
        extended = np.empty(samples.size + 1, dtype=np.complex64)
        extended[0] = self._prev_sample
        extended[1:] = samples
        product = extended[1:] * np.conj(extended[:-1])
        self._prev_sample = samples[-1]
        return np.angle(product).astype(np.float64, copy=False)

    def process(self, block: ChannelizedBlock) -> np.ndarray:
        if block.sample_rate_hz != self._input_rate_hz:
            raise ValueError(
                f"block rate {block.sample_rate_hz} does not match "
                f"demodulator rate {self._input_rate_hz}"
            )
        if block.samples.size == 0:
            return np.zeros(0, dtype=np.float32)

        deviation = self._discriminate(block.samples) * self._gain
        centered, self._dc_state = apply_iir(
            deviation,
            self._dc_b,
            self._dc_a,
            self._dc_state,
        )
        audio, self._audio_state, self._audio_offset = filter_and_decimate(
            centered,
            self._plan.taps,
            self._plan.decimation,
            filter_state=self._audio_state,
            start_offset=self._audio_offset,
        )
        return clip_audio(audio)


class NFMDemodulator(FMDemodulator):
    """Narrow FM — bandwidth is set by the channel filter, not here."""

    MODE: ClassVar[str] = "N-FM"
    DEFAULT_BANDWIDTH_HZ: ClassVar[float] = 12_500.0


class WFMDemodulator(FMDemodulator):
    """Wide FM (broadcast)."""

    MODE: ClassVar[str] = "W-FM"
    DEFAULT_BANDWIDTH_HZ: ClassVar[float] = 200_000.0
