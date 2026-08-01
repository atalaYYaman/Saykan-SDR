"""Unit tests for the listening channel specification."""

from __future__ import annotations

import pytest

from sdr_console.dsp.channel import MIN_CHANNEL_BANDWIDTH_HZ, ChannelSpec

CENTER_HZ = 100_000_000.0
SAMPLE_RATE_HZ = 2_048_000.0


def test_edges_and_offset() -> None:
    channel = ChannelSpec(100_100_000.0, 200_000.0)

    assert channel.low_hz == pytest.approx(100_000_000.0)
    assert channel.high_hz == pytest.approx(100_200_000.0)
    assert channel.offset_from(CENTER_HZ) == pytest.approx(100_000.0)


def test_with_center_and_with_bandwidth_return_copies() -> None:
    channel = ChannelSpec(CENTER_HZ, 200_000.0)

    moved = channel.with_center(100_500_000.0)
    widened = channel.with_bandwidth(300_000.0)

    assert moved.center_freq_hz == pytest.approx(100_500_000.0)
    assert moved.bandwidth_hz == pytest.approx(200_000.0)
    assert widened.bandwidth_hz == pytest.approx(300_000.0)
    assert channel.center_freq_hz == pytest.approx(CENTER_HZ)


@pytest.mark.parametrize("bandwidth_hz", [0.0, -1.0, MIN_CHANNEL_BANDWIDTH_HZ - 1.0])
def test_too_narrow_bandwidth_raises(bandwidth_hz: float) -> None:
    with pytest.raises(ValueError):
        ChannelSpec(CENTER_HZ, bandwidth_hz)


def test_non_finite_values_raise() -> None:
    with pytest.raises(ValueError):
        ChannelSpec(float("nan"), 200_000.0)
    with pytest.raises(ValueError):
        ChannelSpec(CENTER_HZ, float("inf"))


def test_clamped_to_band_pulls_channel_inside_the_visible_span() -> None:
    outside = ChannelSpec(CENTER_HZ + 5_000_000.0, 200_000.0)

    clamped = outside.clamped_to_band(CENTER_HZ, SAMPLE_RATE_HZ)

    assert clamped.bandwidth_hz == pytest.approx(200_000.0)
    assert clamped.high_hz == pytest.approx(CENTER_HZ + SAMPLE_RATE_HZ / 2.0)


def test_clamped_to_band_caps_bandwidth_at_the_span() -> None:
    too_wide = ChannelSpec(CENTER_HZ, 10_000_000.0)

    clamped = too_wide.clamped_to_band(CENTER_HZ, SAMPLE_RATE_HZ)

    assert clamped.bandwidth_hz == pytest.approx(SAMPLE_RATE_HZ)
    assert clamped.center_freq_hz == pytest.approx(CENTER_HZ)


def test_clamped_to_band_keeps_in_band_channel_identical() -> None:
    channel = ChannelSpec(CENTER_HZ + 100_000.0, 200_000.0)

    assert channel.clamped_to_band(CENTER_HZ, SAMPLE_RATE_HZ) is channel
