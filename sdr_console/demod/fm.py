"""Frequency modulation: phase discriminator with deviation normalisation."""

from __future__ import annotations

from typing import ClassVar

import numpy as np

from sdr_console.demod.base import Demodulator
from sdr_console.dsp.afbw import AFBW_SPEECH_HZ, AFBW_WFM_HZ, AudioBandwidthFilter
from sdr_console.dsp.agc import AgcPreset, AutomaticGainControl
from sdr_console.dsp.audio import (
    DEFAULT_AUDIO_RATE_HZ,
    DEFAULT_DC_CUTOFF_HZ,
    apply_iir,
    design_dc_blocker,
    plan_audio_decimation,
    soft_limit_audio,
)
from sdr_console.dsp.channelizer import ChannelizedBlock, filter_and_decimate
from sdr_console.dsp.deemphasis import DEEMPHASIS_TAU_75_US, design_deemphasis


class FMDemodulator(Demodulator):
    """FM via ``angle(x[n] * conj(x[n-1]))``, then DC removal and decimation.

    Discriminator radians are scaled by ``fs / (2π · peak_deviation)`` so a
    full-deviation modulating tone lands near ±1. Optional single-pole
    de-emphasis runs at the audio rate after decimation, then AFBW and a
    light limiter-style AGC. Over-deviation is soft-limited.
    """

    MODE: ClassVar[str]
    DEFAULT_BANDWIDTH_HZ: ClassVar[float]
    PEAK_DEVIATION_HZ: ClassVar[float]
    DEFAULT_DEEMPHASIS: ClassVar[bool] = False
    DEFAULT_AFBW_HZ: ClassVar[float] = AFBW_SPEECH_HZ
    DEFAULT_AGC_ENABLED: ClassVar[bool] = True
    DEFAULT_AGC_PRESET: ClassVar[AgcPreset] = AgcPreset.LIMITER

    def __init__(
        self,
        input_rate_hz: float,
        preferred_audio_rate_hz: float = DEFAULT_AUDIO_RATE_HZ,
        dc_cutoff_hz: float = DEFAULT_DC_CUTOFF_HZ,
        peak_deviation_hz: float | None = None,
        gain: float | None = None,
        audio_decimation: int | None = None,
        deemphasis: bool | None = None,
        deemphasis_tau_s: float | None = None,
        afbw_hz: float | None = None,
        agc_enabled: bool | None = None,
        agc_preset: AgcPreset | str | None = None,
    ) -> None:
        if input_rate_hz <= 0.0:
            raise ValueError("input_rate_hz must be positive")

        self._input_rate_hz = float(input_rate_hz)
        self._peak_deviation_hz = float(
            self.PEAK_DEVIATION_HZ if peak_deviation_hz is None else peak_deviation_hz
        )
        if self._peak_deviation_hz <= 0.0:
            raise ValueError("peak_deviation_hz must be positive")

        # Radians → normalised audio: Δφ · fs / (2π · Δf_peak) ≈ ±1 at full deviation.
        self._gain = (
            float(input_rate_hz / (2.0 * np.pi * self._peak_deviation_hz))
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

        enabled = self.DEFAULT_DEEMPHASIS if deemphasis is None else bool(deemphasis)
        self._deemphasis_enabled = enabled
        self._deemphasis_tau_s: float | None = None
        self._de_b: np.ndarray | None = None
        self._de_a: np.ndarray | None = None
        self._de_state: np.ndarray | None = None
        if enabled:
            tau = DEEMPHASIS_TAU_75_US if deemphasis_tau_s is None else float(deemphasis_tau_s)
            if tau <= 0.0:
                raise ValueError("deemphasis_tau_s must be positive")
            self._deemphasis_tau_s = tau
            self._de_b, self._de_a = design_deemphasis(self._plan.audio_rate_hz, tau)

        cutoff = self.DEFAULT_AFBW_HZ if afbw_hz is None else float(afbw_hz)
        if cutoff <= 0.0:
            raise ValueError("afbw_hz must be positive")
        self._afbw = AudioBandwidthFilter(cutoff, self._plan.audio_rate_hz)

        preset = self.DEFAULT_AGC_PRESET if agc_preset is None else AgcPreset(agc_preset)
        agc_on = self.DEFAULT_AGC_ENABLED if agc_enabled is None else bool(agc_enabled)
        self._agc_preset = preset
        self._agc = AutomaticGainControl.from_preset(
            self._plan.audio_rate_hz, preset, enabled=agc_on
        )

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

    @property
    def peak_deviation_hz(self) -> float:
        """Peak frequency deviation used to normalise discriminator output."""
        return self._peak_deviation_hz

    @property
    def deemphasis_enabled(self) -> bool:
        return self._deemphasis_enabled

    @property
    def deemphasis_tau_s(self) -> float | None:
        """De-emphasis time constant in seconds, or ``None`` when disabled."""
        return self._deemphasis_tau_s

    @property
    def afbw_hz(self) -> float:
        """Audio low-pass cutoff applied after demodulation / de-emphasis."""
        return self._afbw.cutoff_hz

    @property
    def agc_enabled(self) -> bool:
        return self._agc.enabled

    @property
    def agc_preset(self) -> AgcPreset:
        return self._agc_preset

    def reset(self) -> None:
        self._prev_sample = 0.0 + 0.0j
        self._dc_state = None
        self._audio_state = None
        self._audio_offset = 0
        self._de_state = None
        self._afbw.reset()
        self._agc.reset()

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

        normalised = self._discriminate(block.samples) * self._gain
        centered, self._dc_state = apply_iir(
            normalised,
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
        if self._de_b is not None and self._de_a is not None:
            audio, self._de_state = apply_iir(audio, self._de_b, self._de_a, self._de_state)
        audio = self._afbw.process(audio)
        audio = self._agc.process(audio)
        return soft_limit_audio(audio)


class NFMDemodulator(FMDemodulator):
    """Narrow FM — ±5 kHz peak deviation; de-emphasis off unless requested."""

    MODE: ClassVar[str] = "N-FM"
    DEFAULT_BANDWIDTH_HZ: ClassVar[float] = 12_500.0
    PEAK_DEVIATION_HZ: ClassVar[float] = 5_000.0
    DEFAULT_DEEMPHASIS: ClassVar[bool] = False
    DEFAULT_AFBW_HZ: ClassVar[float] = AFBW_SPEECH_HZ
    DEFAULT_AGC_PRESET: ClassVar[AgcPreset] = AgcPreset.LIMITER


class WFMDemodulator(FMDemodulator):
    """Wide FM (broadcast) — ±75 kHz peak deviation; de-emphasis on by default."""

    MODE: ClassVar[str] = "W-FM"
    DEFAULT_BANDWIDTH_HZ: ClassVar[float] = 200_000.0
    PEAK_DEVIATION_HZ: ClassVar[float] = 75_000.0
    DEFAULT_DEEMPHASIS: ClassVar[bool] = True
    DEFAULT_AFBW_HZ: ClassVar[float] = AFBW_WFM_HZ
    DEFAULT_AGC_PRESET: ClassVar[AgcPreset] = AgcPreset.LIMITER
