"""Mock SDR device that emits absolute-RF tones plus noise for testing."""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from sdr_console.hal.capabilities import DeviceCapabilities
from sdr_console.hal.interface import SDRDeviceInterface

# RTL-SDR-like limits so UI tuning code can be exercised early.
MOCK_CAPABILITIES = DeviceCapabilities(
    min_freq_hz=25_000_000.0,
    max_freq_hz=1_750_000_000.0,
    supported_sample_rates_hz=(
        250_000.0,
        1_024_000.0,
        2_048_000.0,
        2_400_000.0,
        2_560_000.0,
        3_200_000.0,
    ),
    min_gain_db=0.0,
    max_gain_db=50.0,
)

DEFAULT_CENTER_FREQ_HZ = 100_000_000.0
DEFAULT_TONE_OFFSETS_HZ: tuple[float, ...] = (
    -180_000.0,
    -75_000.0,
    50_000.0,
    120_000.0,
    250_000.0,
)
DEFAULT_TONE_AMPLITUDES: tuple[float, ...] = (0.35, 0.55, 1.0, 0.45, 0.25)


@dataclass(frozen=True)
class MockTone:
    """Absolute RF tone that appears when inside the receiver bandwidth."""

    frequency_hz: float
    relative_amplitude: float = 1.0


def default_tones(center_freq_hz: float = DEFAULT_CENTER_FREQ_HZ) -> tuple[MockTone, ...]:
    """Build the default absolute-RF tone set around ``center_freq_hz``."""
    return tuple(
        MockTone(center_freq_hz + offset, amp)
        for offset, amp in zip(DEFAULT_TONE_OFFSETS_HZ, DEFAULT_TONE_AMPLITUDES, strict=True)
    )


class MockSDRDevice(SDRDeviceInterface):
    """Synthetic IQ source: absolute-RF tones + AWGN at the configured rate."""

    def __init__(
        self,
        sample_rate_hz: float = 2_048_000.0,
        center_freq_hz: float = DEFAULT_CENTER_FREQ_HZ,
        gain_db: float = 20.0,
        tones: tuple[MockTone, ...] | None = None,
        noise_amplitude: float = 0.05,
        capabilities: DeviceCapabilities = MOCK_CAPABILITIES,
        rng: np.random.Generator | None = None,
        realtime: bool = False,
    ) -> None:
        self._capabilities = capabilities
        self._center_freq_hz = center_freq_hz
        self._sample_rate_hz = sample_rate_hz
        self._gain_db = gain_db
        self._noise_amplitude = noise_amplitude
        self._rng = rng or np.random.default_rng(42)
        self._realtime = realtime
        self._connected = False
        self._sample_index = 0
        self._stream_start_s: float | None = None
        self._tones = tones if tones is not None else default_tones(center_freq_hz)

        self._capabilities.validate_freq_hz(center_freq_hz)
        self._capabilities.validate_sample_rate_hz(sample_rate_hz)
        self._capabilities.validate_gain_db(gain_db)

    @property
    def capabilities(self) -> DeviceCapabilities:
        return self._capabilities

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def center_freq_hz(self) -> float:
        return self._center_freq_hz

    @property
    def sample_rate_hz(self) -> float:
        return self._sample_rate_hz

    @property
    def gain_db(self) -> float:
        return self._gain_db

    @property
    def realtime(self) -> bool:
        return self._realtime

    @realtime.setter
    def realtime(self, value: bool) -> None:
        self._realtime = value

    def connect(self) -> None:
        self._connected = True
        self._sample_index = 0
        self._stream_start_s = None

    def disconnect(self) -> None:
        self._connected = False

    def set_center_freq(self, freq_hz: float) -> None:
        self._capabilities.validate_freq_hz(freq_hz)
        self._center_freq_hz = freq_hz

    def set_sample_rate(self, rate_hz: float) -> None:
        self._capabilities.validate_sample_rate_hz(rate_hz)
        self._sample_rate_hz = rate_hz

    def set_gain(self, gain_db: float) -> None:
        self._capabilities.validate_gain_db(gain_db)
        self._gain_db = gain_db

    def _pace(self, num_samples: int) -> None:
        """Block until these samples would have arrived on a real device.

        Waits against an absolute schedule instead of sleeping per block: the OS
        timer overshoots short sleeps, and per-block sleeps let that overshoot
        accumulate until the stream runs slower than its own sample rate — which
        starves anything downstream that plays in real time, such as audio.
        """
        if not self._realtime:
            return
        if self._stream_start_s is None:
            self._stream_start_s = time.monotonic()

        due_s = self._stream_start_s + (self._sample_index + num_samples) / self._sample_rate_hz
        delay_s = due_s - time.monotonic()
        if delay_s > 0.0:
            time.sleep(delay_s)

    def read_samples(self, num_samples: int) -> np.ndarray:
        if not self._connected:
            raise RuntimeError("MockSDRDevice is not connected")
        if num_samples <= 0:
            raise ValueError("num_samples must be positive")

        self._pace(num_samples)

        sample_indices = self._sample_index + np.arange(num_samples, dtype=np.float64)
        signal = np.zeros(num_samples, dtype=np.complex128)
        # Full-scale amplitude at max gain so DSP dBFS peaks near 0 dB.
        gain_scale = 10 ** (
            (self._gain_db - self._capabilities.max_gain_db) / 20.0
        )

        nyquist = self._sample_rate_hz / 2.0
        for tone in self._tones:
            offset_hz = tone.frequency_hz - self._center_freq_hz
            if abs(offset_hz) >= nyquist:
                continue  # out of band: real receivers do not show it

            phase_radians = (
                2.0 * np.pi * offset_hz * sample_indices / self._sample_rate_hz
            )
            signal += (
                gain_scale
                * tone.relative_amplitude
                * np.exp(1j * phase_radians)
            )

        noise = self._noise_amplitude * (
            self._rng.standard_normal(num_samples)
            + 1j * self._rng.standard_normal(num_samples)
        )

        self._sample_index += num_samples
        return (signal + noise).astype(np.complex64)
