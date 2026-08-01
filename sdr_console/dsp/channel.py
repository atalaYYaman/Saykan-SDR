"""Channel (listening band) description.

``ChannelSpec`` is the shared vocabulary for "which slice of the spectrum am I
listening to": the viz layer draws it as an overlay box, and later steps feed it
to the band-pass filter / demodulation chain. It lives in ``dsp`` because it is
the lowest layer both viz and the demod pipeline already depend on.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from sdr_console.dsp.axis import band_edges_hz

MIN_CHANNEL_BANDWIDTH_HZ = 100.0


@dataclass(frozen=True)
class ChannelSpec:
    """Absolute RF channel: center frequency plus bandwidth, both in Hz."""

    center_freq_hz: float
    bandwidth_hz: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.center_freq_hz):
            raise ValueError("center_freq_hz must be finite")
        if not math.isfinite(self.bandwidth_hz):
            raise ValueError("bandwidth_hz must be finite")
        if self.bandwidth_hz < MIN_CHANNEL_BANDWIDTH_HZ:
            raise ValueError(
                f"bandwidth_hz must be at least {MIN_CHANNEL_BANDWIDTH_HZ} Hz"
            )

    @property
    def low_hz(self) -> float:
        """Lower channel edge in Hz."""
        return self.center_freq_hz - self.bandwidth_hz / 2.0

    @property
    def high_hz(self) -> float:
        """Upper channel edge in Hz."""
        return self.center_freq_hz + self.bandwidth_hz / 2.0

    def offset_from(self, device_center_freq_hz: float) -> float:
        """Baseband offset of this channel relative to the receiver center."""
        return self.center_freq_hz - float(device_center_freq_hz)

    def with_bandwidth(self, bandwidth_hz: float) -> ChannelSpec:
        """Return a copy with a different bandwidth."""
        return ChannelSpec(self.center_freq_hz, float(bandwidth_hz))

    def with_center(self, center_freq_hz: float) -> ChannelSpec:
        """Return a copy tuned to a different center frequency."""
        return ChannelSpec(float(center_freq_hz), self.bandwidth_hz)

    def clamped_to_band(
        self,
        device_center_freq_hz: float,
        sample_rate_hz: float,
    ) -> ChannelSpec:
        """Return a spec that fits entirely inside the observable band.

        Bandwidth is capped at the band span first, then the center frequency is
        pulled inside so both edges stay visible.
        """
        low_hz, high_hz = band_edges_hz(device_center_freq_hz, sample_rate_hz)
        span_hz = high_hz - low_hz

        bandwidth_hz = max(min(self.bandwidth_hz, span_hz), MIN_CHANNEL_BANDWIDTH_HZ)
        half_bandwidth = bandwidth_hz / 2.0
        center_hz = min(
            max(self.center_freq_hz, low_hz + half_bandwidth),
            high_hz - half_bandwidth,
        )

        if center_hz == self.center_freq_hz and bandwidth_hz == self.bandwidth_hz:
            return self
        return ChannelSpec(center_hz, bandwidth_hz)
