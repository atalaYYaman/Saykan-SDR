"""Reusable mock tone scenarios for testing and demos."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from sdr_console.hal.capabilities import DeviceCapabilities
from sdr_console.hal.mock_device import (
    DEFAULT_CENTER_FREQ_HZ,
    MOCK_CAPABILITIES,
    MockSDRDevice,
    MockTone,
)


@dataclass(frozen=True)
class SweepToneSpec:
    """Linear frequency sweep around the initial center frequency."""

    start_freq_hz: float
    end_freq_hz: float
    duration_s: float
    relative_amplitude: float = 1.0


class SweepMockDevice(MockSDRDevice):
    """Mock device whose single tone sweeps across a frequency range."""

    def __init__(
        self,
        sweep: SweepToneSpec,
        sample_rate_hz: float = 2_048_000.0,
        center_freq_hz: float = DEFAULT_CENTER_FREQ_HZ,
        gain_db: float = 20.0,
        noise_amplitude: float = 0.01,
        capabilities: DeviceCapabilities = MOCK_CAPABILITIES,
        rng: np.random.Generator | None = None,
        realtime: bool = False,
    ) -> None:
        super().__init__(
            sample_rate_hz=sample_rate_hz,
            center_freq_hz=center_freq_hz,
            gain_db=gain_db,
            tones=(),
            noise_amplitude=noise_amplitude,
            capabilities=capabilities,
            rng=rng,
            realtime=realtime,
        )
        self._sweep = sweep
        self._phase = 0.0

    def connect(self) -> None:
        super().connect()
        self._phase = 0.0

    def read_samples(self, num_samples: int) -> np.ndarray:
        if not self._connected:
            raise RuntimeError("SweepMockDevice is not connected")
        if num_samples <= 0:
            raise ValueError("num_samples must be positive")

        self._pace(num_samples)

        t0 = self._sample_index / self._sample_rate_hz
        sample_times = t0 + np.arange(num_samples, dtype=np.float64) / self._sample_rate_hz
        duration = max(self._sweep.duration_s, 1e-9)
        progress = np.clip(sample_times / duration, 0.0, 1.0)
        tone_freq = (
            self._sweep.start_freq_hz
            + (self._sweep.end_freq_hz - self._sweep.start_freq_hz) * progress
        )
        offset_hz = tone_freq - self._center_freq_hz

        gain_scale = 10 ** (
            (self._gain_db - self._capabilities.max_gain_db) / 20.0
        )
        phase_inc = 2.0 * np.pi * offset_hz / self._sample_rate_hz
        phase = self._phase + np.cumsum(phase_inc)
        signal = (
            gain_scale
            * self._sweep.relative_amplitude
            * np.exp(1j * phase)
        )
        self._phase = float(phase[-1] % (2.0 * np.pi))

        noise = self._noise_amplitude * (
            self._rng.standard_normal(num_samples)
            + 1j * self._rng.standard_normal(num_samples)
        )
        self._sample_index += num_samples
        return (signal + noise).astype(np.complex64)


@dataclass(frozen=True)
class BurstToneSpec:
    """Periodic on/off burst transmission at a fixed RF frequency."""

    frequency_hz: float
    period_s: float
    duty_cycle: float = 0.5
    relative_amplitude: float = 1.0


class BurstMockDevice(MockSDRDevice):
    """Mock device that gates a tone with a duty cycle."""

    def __init__(
        self,
        burst: BurstToneSpec,
        sample_rate_hz: float = 2_048_000.0,
        center_freq_hz: float = DEFAULT_CENTER_FREQ_HZ,
        gain_db: float = 20.0,
        noise_amplitude: float = 0.01,
        capabilities: DeviceCapabilities = MOCK_CAPABILITIES,
        rng: np.random.Generator | None = None,
        realtime: bool = False,
    ) -> None:
        super().__init__(
            sample_rate_hz=sample_rate_hz,
            center_freq_hz=center_freq_hz,
            gain_db=gain_db,
            tones=(MockTone(burst.frequency_hz, burst.relative_amplitude),),
            noise_amplitude=noise_amplitude,
            capabilities=capabilities,
            rng=rng,
            realtime=realtime,
        )
        self._burst = burst

    def read_samples(self, num_samples: int) -> np.ndarray:
        samples = super().read_samples(num_samples)
        t0 = (self._sample_index - num_samples) / self._sample_rate_hz
        sample_times = t0 + np.arange(num_samples, dtype=np.float64) / self._sample_rate_hz
        period = max(self._burst.period_s, 1e-9)
        phase_in_period = np.mod(sample_times, period) / period
        gate = (phase_in_period < self._burst.duty_cycle).astype(np.float32)
        # Keep noise floor; gate only the coherent part approximately by
        # re-adding ungated noise when off. Simpler: multiply full sample.
        gated = samples * gate
        noise = self._noise_amplitude * (
            self._rng.standard_normal(num_samples)
            + 1j * self._rng.standard_normal(num_samples)
        ).astype(np.complex64)
        off = gate < 0.5
        gated[off] = noise[off]
        return gated


@dataclass(frozen=True)
class AMSignalSpec:
    """Amplitude-modulated carrier whose envelope carries one audio tone."""

    carrier_freq_hz: float
    audio_freq_hz: float = 1_000.0
    modulation_index: float = 0.5
    relative_amplitude: float = 0.8


class AMMockDevice(MockSDRDevice):
    """Mock device emitting an AM-modulated carrier, for demodulation tests."""

    def __init__(
        self,
        am: AMSignalSpec,
        sample_rate_hz: float = 2_048_000.0,
        center_freq_hz: float = DEFAULT_CENTER_FREQ_HZ,
        gain_db: float = MOCK_CAPABILITIES.max_gain_db,
        noise_amplitude: float = 0.0,
        capabilities: DeviceCapabilities = MOCK_CAPABILITIES,
        rng: np.random.Generator | None = None,
        realtime: bool = False,
    ) -> None:
        super().__init__(
            sample_rate_hz=sample_rate_hz,
            center_freq_hz=center_freq_hz,
            gain_db=gain_db,
            tones=(),
            noise_amplitude=noise_amplitude,
            capabilities=capabilities,
            rng=rng,
            realtime=realtime,
        )
        self._am = am
        self._carrier_phase = 0.0
        self._audio_phase = 0.0

    @property
    def am(self) -> AMSignalSpec:
        return self._am

    def connect(self) -> None:
        super().connect()
        self._carrier_phase = 0.0
        self._audio_phase = 0.0

    def read_samples(self, num_samples: int) -> np.ndarray:
        if not self._connected:
            raise RuntimeError("AMMockDevice is not connected")
        if num_samples <= 0:
            raise ValueError("num_samples must be positive")

        self._pace(num_samples)

        indices = np.arange(num_samples, dtype=np.float64)
        noise = self._noise_amplitude * (
            self._rng.standard_normal(num_samples)
            + 1j * self._rng.standard_normal(num_samples)
        )
        self._sample_index += num_samples

        offset_hz = self._am.carrier_freq_hz - self._center_freq_hz
        if abs(offset_hz) >= self._sample_rate_hz / 2.0:
            return noise.astype(np.complex64)  # out of band: noise only

        audio_step = 2.0 * np.pi * self._am.audio_freq_hz / self._sample_rate_hz
        audio_phase = self._audio_phase + audio_step * indices
        envelope = self._am.relative_amplitude * (
            1.0 + self._am.modulation_index * np.sin(audio_phase)
        )

        carrier_step = 2.0 * np.pi * offset_hz / self._sample_rate_hz
        carrier_phase = self._carrier_phase + carrier_step * indices

        gain_scale = 10 ** ((self._gain_db - self._capabilities.max_gain_db) / 20.0)
        signal = gain_scale * envelope * np.exp(1j * carrier_phase)

        two_pi = 2.0 * np.pi
        self._audio_phase = float((self._audio_phase + audio_step * num_samples) % two_pi)
        self._carrier_phase = float(
            (self._carrier_phase + carrier_step * num_samples) % two_pi
        )

        return (signal + noise).astype(np.complex64)


def noise_only(
    sample_rate_hz: float = 2_048_000.0,
    center_freq_hz: float = DEFAULT_CENTER_FREQ_HZ,
    gain_db: float = 20.0,
    noise_amplitude: float = 0.05,
    realtime: bool = False,
) -> MockSDRDevice:
    """Empty band: AWGN only, no coherent tones."""
    return MockSDRDevice(
        sample_rate_hz=sample_rate_hz,
        center_freq_hz=center_freq_hz,
        gain_db=gain_db,
        tones=(),
        noise_amplitude=noise_amplitude,
        realtime=realtime,
    )


def clipping_source(
    sample_rate_hz: float = 2_048_000.0,
    center_freq_hz: float = DEFAULT_CENTER_FREQ_HZ,
    tone_offset_hz: float = 50_000.0,
    realtime: bool = False,
) -> MockSDRDevice:
    """Saturated tone near full scale for display-limit testing."""
    return MockSDRDevice(
        sample_rate_hz=sample_rate_hz,
        center_freq_hz=center_freq_hz,
        gain_db=MOCK_CAPABILITIES.max_gain_db,
        tones=(MockTone(center_freq_hz + tone_offset_hz, 1.0),),
        noise_amplitude=0.0,
        realtime=realtime,
    )


def sweep_tone(
    start_offset_hz: float = -200_000.0,
    end_offset_hz: float = 200_000.0,
    duration_s: float = 2.0,
    center_freq_hz: float = DEFAULT_CENTER_FREQ_HZ,
    sample_rate_hz: float = 2_048_000.0,
    realtime: bool = False,
) -> SweepMockDevice:
    """Convenience factory for a linear frequency sweep."""
    return SweepMockDevice(
        sweep=SweepToneSpec(
            start_freq_hz=center_freq_hz + start_offset_hz,
            end_freq_hz=center_freq_hz + end_offset_hz,
            duration_s=duration_s,
        ),
        sample_rate_hz=sample_rate_hz,
        center_freq_hz=center_freq_hz,
        realtime=realtime,
    )


def am_tone(
    offset_hz: float = 50_000.0,
    audio_freq_hz: float = 1_000.0,
    modulation_index: float = 0.5,
    center_freq_hz: float = DEFAULT_CENTER_FREQ_HZ,
    sample_rate_hz: float = 2_048_000.0,
    noise_amplitude: float = 0.0,
    realtime: bool = False,
) -> AMMockDevice:
    """Convenience factory for an AM-modulated carrier at ``offset_hz``."""
    return AMMockDevice(
        am=AMSignalSpec(
            carrier_freq_hz=center_freq_hz + offset_hz,
            audio_freq_hz=audio_freq_hz,
            modulation_index=modulation_index,
        ),
        sample_rate_hz=sample_rate_hz,
        center_freq_hz=center_freq_hz,
        noise_amplitude=noise_amplitude,
        realtime=realtime,
    )


def burst_tone(
    offset_hz: float = 50_000.0,
    period_s: float = 0.2,
    duty_cycle: float = 0.5,
    center_freq_hz: float = DEFAULT_CENTER_FREQ_HZ,
    sample_rate_hz: float = 2_048_000.0,
    realtime: bool = False,
) -> BurstMockDevice:
    """Convenience factory for an on/off burst tone."""
    return BurstMockDevice(
        burst=BurstToneSpec(
            frequency_hz=center_freq_hz + offset_hz,
            period_s=period_s,
            duty_cycle=duty_cycle,
        ),
        sample_rate_hz=sample_rate_hz,
        center_freq_hz=center_freq_hz,
        realtime=realtime,
    )
