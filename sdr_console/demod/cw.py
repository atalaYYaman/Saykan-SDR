"""Continuous-wave (Morse) demodulation with a beat-frequency oscillator."""

from __future__ import annotations

from typing import ClassVar

import numpy as np

from sdr_console.demod.base import Demodulator
from sdr_console.dsp.afbw import AFBW_CW_HZ, AudioBandwidthFilter
from sdr_console.dsp.agc import AgcPreset, AutomaticGainControl
from sdr_console.dsp.audio import (
    DEFAULT_AUDIO_RATE_HZ,
    DEFAULT_DC_CUTOFF_HZ,
    apply_iir,
    clip_audio,
    design_dc_blocker,
    plan_audio_decimation,
)
from sdr_console.dsp.channelizer import ChannelizedBlock, filter_and_decimate

DEFAULT_BFO_OFFSET_HZ = 750.0


class CWDemodulator(Demodulator):
    """Product detector: mix the CW carrier with a fixed audio-frequency BFO.

    A narrow RF carrier becomes an audible tone at ``bfo_offset_hz`` when the
    listening frequency is on the carrier. Narrow AFBW and fast AGC follow.
    """

    MODE: ClassVar[str] = "CW"
    DEFAULT_BANDWIDTH_HZ: ClassVar[float] = 500.0
    DEFAULT_AFBW_HZ: ClassVar[float] = AFBW_CW_HZ
    DEFAULT_AGC_ENABLED: ClassVar[bool] = True
    DEFAULT_AGC_PRESET: ClassVar[AgcPreset] = AgcPreset.FAST

    def __init__(
        self,
        input_rate_hz: float,
        preferred_audio_rate_hz: float = DEFAULT_AUDIO_RATE_HZ,
        bfo_offset_hz: float = DEFAULT_BFO_OFFSET_HZ,
        dc_cutoff_hz: float = DEFAULT_DC_CUTOFF_HZ,
        gain: float = 2.0,
        audio_decimation: int | None = None,
        afbw_hz: float | None = None,
        agc_enabled: bool | None = None,
        agc_preset: AgcPreset | str | None = None,
    ) -> None:
        if input_rate_hz <= 0.0:
            raise ValueError("input_rate_hz must be positive")
        if bfo_offset_hz <= 0.0:
            raise ValueError("bfo_offset_hz must be positive")
        if gain <= 0.0:
            raise ValueError("gain must be positive")

        self._input_rate_hz = float(input_rate_hz)
        self._bfo_offset_hz = float(bfo_offset_hz)
        self._gain = float(gain)
        self._plan = plan_audio_decimation(
            self._input_rate_hz,
            preferred_audio_rate_hz,
            decimation=audio_decimation,
        )
        self._dc_b, self._dc_a = design_dc_blocker(self._input_rate_hz, dc_cutoff_hz)

        cutoff = self.DEFAULT_AFBW_HZ if afbw_hz is None else float(afbw_hz)
        if cutoff <= 0.0:
            raise ValueError("afbw_hz must be positive")
        self._afbw = AudioBandwidthFilter(cutoff, self._plan.audio_rate_hz)

        preset = self.DEFAULT_AGC_PRESET if agc_preset is None else AgcPreset(agc_preset)
        enabled = self.DEFAULT_AGC_ENABLED if agc_enabled is None else bool(agc_enabled)
        self._agc_preset = preset
        self._agc = AutomaticGainControl.from_preset(
            self._plan.audio_rate_hz, preset, enabled=enabled
        )

        self._bfo_phase = 0.0
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
    def bfo_offset_hz(self) -> float:
        return self._bfo_offset_hz

    @property
    def decimation(self) -> int:
        return self._plan.decimation

    @property
    def afbw_hz(self) -> float:
        return self._afbw.cutoff_hz

    @property
    def agc_enabled(self) -> bool:
        return self._agc.enabled

    @property
    def agc_preset(self) -> AgcPreset:
        return self._agc_preset

    def reset(self) -> None:
        self._bfo_phase = 0.0
        self._dc_state = None
        self._audio_state = None
        self._audio_offset = 0
        self._afbw.reset()
        self._agc.reset()

    def _mix_with_bfo(self, samples: np.ndarray) -> np.ndarray:
        count = samples.size
        step = 2.0 * np.pi * self._bfo_offset_hz / self._input_rate_hz
        indices = np.arange(count, dtype=np.float64)
        phase = self._bfo_phase + step * indices
        oscillator = np.exp(1j * phase)
        self._bfo_phase = float((self._bfo_phase + step * count) % (2.0 * np.pi))
        return np.real(samples * oscillator)

    def process(self, block: ChannelizedBlock) -> np.ndarray:
        if block.sample_rate_hz != self._input_rate_hz:
            raise ValueError(
                f"block rate {block.sample_rate_hz} does not match "
                f"demodulator rate {self._input_rate_hz}"
            )
        if block.samples.size == 0:
            return np.zeros(0, dtype=np.float32)

        detected = self._mix_with_bfo(block.samples) * self._gain
        centered, self._dc_state = apply_iir(
            detected,
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
        audio = self._agc.process(self._afbw.process(audio))
        return clip_audio(audio)
