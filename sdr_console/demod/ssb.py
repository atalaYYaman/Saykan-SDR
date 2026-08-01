"""Single-sideband demodulation from complex baseband."""

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


class SSBDemodulator(Demodulator):
    """Extract one sideband from a channel already mixed to baseband.

    USB keeps the in-phase (real) component; LSB keeps quadrature with the sign
    convention used throughout this project (``-imag``).
    """

    MODE: ClassVar[str]
    DEFAULT_BANDWIDTH_HZ: ClassVar[float]
    _COMPONENT: ClassVar[str]

    def __init__(
        self,
        input_rate_hz: float,
        preferred_audio_rate_hz: float = DEFAULT_AUDIO_RATE_HZ,
        dc_cutoff_hz: float = DEFAULT_DC_CUTOFF_HZ,
        gain: float = 1.0,
        audio_decimation: int | None = None,
    ) -> None:
        if input_rate_hz <= 0.0:
            raise ValueError("input_rate_hz must be positive")
        if gain <= 0.0:
            raise ValueError("gain must be positive")

        self._input_rate_hz = float(input_rate_hz)
        self._gain = float(gain)
        self._plan = plan_audio_decimation(
            self._input_rate_hz,
            preferred_audio_rate_hz,
            decimation=audio_decimation,
        )
        self._dc_b, self._dc_a = design_dc_blocker(self._input_rate_hz, dc_cutoff_hz)

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
        self._dc_state = None
        self._audio_state = None
        self._audio_offset = 0

    def _extract(self, samples: np.ndarray) -> np.ndarray:
        if self._COMPONENT == "real":
            return np.real(samples)
        return -np.imag(samples)

    def process(self, block: ChannelizedBlock) -> np.ndarray:
        if block.sample_rate_hz != self._input_rate_hz:
            raise ValueError(
                f"block rate {block.sample_rate_hz} does not match "
                f"demodulator rate {self._input_rate_hz}"
            )
        if block.samples.size == 0:
            return np.zeros(0, dtype=np.float32)

        baseband = self._extract(block.samples).astype(np.float64, copy=False)
        centered, self._dc_state = apply_iir(
            baseband * self._gain,
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


class USBDemodulator(SSBDemodulator):
    """Upper sideband."""

    MODE: ClassVar[str] = "USB"
    DEFAULT_BANDWIDTH_HZ: ClassVar[float] = 2_700.0
    _COMPONENT: ClassVar[str] = "real"


class LSBDemodulator(SSBDemodulator):
    """Lower sideband."""

    MODE: ClassVar[str] = "LSB"
    DEFAULT_BANDWIDTH_HZ: ClassVar[float] = 2_700.0
    _COMPONENT: ClassVar[str] = "imag"
