"""Unit tests for channel mixing, filtering and decimation."""

from __future__ import annotations

import numpy as np
import pytest

from sdr_console.dsp.channel import ChannelSpec
from sdr_console.dsp.channelizer import (
    MAX_FILTER_TAPS,
    MIN_FILTER_TAPS,
    ChannelizerState,
    channelize,
    choose_decimation,
    design_channel_filter,
    filter_and_decimate,
    frequency_shift,
    plan_channelizer,
)

CENTER_HZ = 100_000_000.0
SAMPLE_RATE_HZ = 2_048_000.0
TARGET_RATE_HZ = 48_000.0
BLOCK = 16_384


def make_tone(offset_hz: float, num_samples: int, start_index: int = 0) -> np.ndarray:
    """Complex tone at baseband offset ``offset_hz`` (relative to receiver center)."""
    indices = np.arange(start_index, start_index + num_samples, dtype=np.float64)
    phase = 2.0 * np.pi * offset_hz * indices / SAMPLE_RATE_HZ
    return np.exp(1j * phase).astype(np.complex64)


def test_choose_decimation_respects_bandwidth_and_target_rate() -> None:
    # 200 kHz channel cannot be decimated below its own bandwidth.
    assert choose_decimation(SAMPLE_RATE_HZ, 200_000.0, TARGET_RATE_HZ) == 10
    # A narrow channel is limited by the requested output rate instead.
    assert choose_decimation(SAMPLE_RATE_HZ, 3_000.0, TARGET_RATE_HZ) == 42
    # Never below 1, even when the target rate exceeds the input rate.
    assert choose_decimation(SAMPLE_RATE_HZ, 200_000.0, 10_000_000.0) == 1


@pytest.mark.parametrize("bad_value", [0.0, -1.0])
def test_choose_decimation_rejects_non_positive_arguments(bad_value: float) -> None:
    with pytest.raises(ValueError):
        choose_decimation(bad_value, 200_000.0, TARGET_RATE_HZ)
    with pytest.raises(ValueError):
        choose_decimation(SAMPLE_RATE_HZ, bad_value, TARGET_RATE_HZ)
    with pytest.raises(ValueError):
        choose_decimation(SAMPLE_RATE_HZ, 200_000.0, bad_value)


def test_filter_has_unity_dc_gain_and_odd_bounded_length() -> None:
    taps = design_channel_filter(200_000.0, SAMPLE_RATE_HZ, 204_800.0)

    assert taps.size % 2 == 1
    assert MIN_FILTER_TAPS <= taps.size <= MAX_FILTER_TAPS
    assert taps.sum() == pytest.approx(1.0, abs=1e-6)


def test_filter_passes_channel_and_stops_out_of_band() -> None:
    bandwidth_hz = 200_000.0
    taps = design_channel_filter(bandwidth_hz, SAMPLE_RATE_HZ, 204_800.0)
    response = np.fft.rfft(taps, n=8192)
    freqs = np.fft.rfftfreq(8192, d=1.0 / SAMPLE_RATE_HZ)
    magnitude_db = 20.0 * np.log10(np.maximum(np.abs(response), 1e-12))

    in_band = magnitude_db[freqs <= bandwidth_hz / 2.0 * 0.8]
    far_out = magnitude_db[freqs >= 200_000.0]

    assert np.all(in_band > -1.0)
    assert np.all(far_out < -40.0)


def test_passthrough_filter_when_channel_covers_the_whole_band() -> None:
    taps = design_channel_filter(SAMPLE_RATE_HZ, SAMPLE_RATE_HZ, SAMPLE_RATE_HZ)

    assert taps.size == 1
    assert taps[0] == pytest.approx(1.0)


def test_frequency_shift_moves_the_tone_to_dc() -> None:
    offset_hz = 250_000.0
    iq = make_tone(offset_hz, 4096)

    mixed, _ = frequency_shift(iq, offset_hz, SAMPLE_RATE_HZ)

    # A tone mixed by its own frequency becomes a constant (DC) phasor.
    assert np.std(np.angle(mixed)) == pytest.approx(0.0, abs=1e-4)
    assert np.mean(np.abs(mixed)) == pytest.approx(1.0, abs=1e-3)


def test_frequency_shift_is_continuous_across_blocks() -> None:
    offset_hz = 137_000.0
    whole = make_tone(offset_hz, 2048)

    single, _ = frequency_shift(whole, offset_hz, SAMPLE_RATE_HZ)
    first, phase = frequency_shift(whole[:1024], offset_hz, SAMPLE_RATE_HZ)
    second, _ = frequency_shift(whole[1024:], offset_hz, SAMPLE_RATE_HZ, start_phase_rad=phase)

    stitched = np.concatenate([first, second])
    np.testing.assert_allclose(stitched, single, atol=1e-4)


def test_filter_and_decimate_keeps_the_sampling_grid_across_blocks() -> None:
    taps = np.ones(1, dtype=np.float64)
    samples = np.arange(10, dtype=np.complex64)

    whole, _, _ = filter_and_decimate(samples, taps, 3)
    first, state, offset = filter_and_decimate(samples[:4], taps, 3)
    second, _, _ = filter_and_decimate(
        samples[4:], taps, 3, filter_state=state, start_offset=offset
    )

    np.testing.assert_allclose(np.concatenate([first, second]), whole)
    np.testing.assert_allclose(whole, np.array([0.0, 3.0, 6.0, 9.0]))


def test_filter_and_decimate_rejects_invalid_arguments() -> None:
    samples = np.zeros(8, dtype=np.complex64)
    taps = np.ones(1, dtype=np.float64)

    with pytest.raises(ValueError):
        filter_and_decimate(samples, taps, 0)
    with pytest.raises(ValueError):
        filter_and_decimate(samples, np.array([], dtype=np.float64), 2)
    with pytest.raises(ValueError):
        filter_and_decimate(samples, taps, 2, start_offset=2)


def test_plan_channelizer_output_rate_matches_decimation() -> None:
    plan = plan_channelizer(200_000.0, SAMPLE_RATE_HZ, TARGET_RATE_HZ)

    assert plan.decimation == 10
    assert plan.output_rate_hz == pytest.approx(204_800.0)
    assert plan.output_rate_hz >= 200_000.0
    assert plan.num_taps == plan.taps.size


def test_channelize_extracts_an_in_band_tone_at_full_amplitude() -> None:
    channel = ChannelSpec(CENTER_HZ + 250_000.0, 200_000.0)
    plan = plan_channelizer(channel.bandwidth_hz, SAMPLE_RATE_HZ, TARGET_RATE_HZ)
    # Tone 20 kHz off the channel center, i.e. well inside the 200 kHz channel.
    iq = make_tone(270_000.0, BLOCK)

    block, state = channelize(iq, channel, CENTER_HZ, SAMPLE_RATE_HZ, plan)

    assert block.sample_rate_hz == pytest.approx(204_800.0)
    assert block.samples.dtype == np.complex64
    assert block.samples.size == pytest.approx(BLOCK / plan.decimation, abs=1)
    # Skip the filter warm-up region before measuring amplitude.
    settled = block.samples[plan.num_taps // plan.decimation + 1 :]
    assert np.mean(np.abs(settled)) == pytest.approx(1.0, abs=0.05)
    assert isinstance(state, ChannelizerState)


def test_channelize_suppresses_a_tone_outside_the_channel() -> None:
    channel = ChannelSpec(CENTER_HZ, 200_000.0)
    plan = plan_channelizer(channel.bandwidth_hz, SAMPLE_RATE_HZ, TARGET_RATE_HZ)
    inside = make_tone(0.0, BLOCK)
    outside = make_tone(500_000.0, BLOCK)

    kept, _ = channelize(inside, channel, CENTER_HZ, SAMPLE_RATE_HZ, plan)
    rejected, _ = channelize(outside, channel, CENTER_HZ, SAMPLE_RATE_HZ, plan)

    settled = slice(plan.num_taps // plan.decimation + 1, None)
    kept_level = float(np.mean(np.abs(kept.samples[settled])))
    rejected_level = float(np.mean(np.abs(rejected.samples[settled])))

    assert 20.0 * np.log10(rejected_level / kept_level) < -40.0


@pytest.mark.parametrize(
    "bandwidth_hz",
    [
        500.0,  # CW
        2_700.0,  # SSB
        10_000.0,  # AM
        12_500.0,  # N-FM
        200_000.0,  # W-FM
    ],
)
def test_mode_default_rfbw_keeps_in_band_and_rejects_out_of_band(
    bandwidth_hz: float,
) -> None:
    """Synthetic tones: inside RFBW stays, outside is attenuated (A1)."""
    channel = ChannelSpec(CENTER_HZ, bandwidth_hz)
    plan = plan_channelizer(channel.bandwidth_hz, SAMPLE_RATE_HZ, TARGET_RATE_HZ)
    half_bw = bandwidth_hz / 2.0
    # Well inside the passband; well outside the stop edge.
    inside_offset_hz = half_bw * 0.25
    outside_offset_hz = max(bandwidth_hz * 4.0, half_bw + 50_000.0)

    inside = make_tone(inside_offset_hz, BLOCK)
    outside = make_tone(outside_offset_hz, BLOCK)

    kept, _ = channelize(inside, channel, CENTER_HZ, SAMPLE_RATE_HZ, plan)
    rejected, _ = channelize(outside, channel, CENTER_HZ, SAMPLE_RATE_HZ, plan)

    settled = slice(plan.num_taps // plan.decimation + 1, None)
    kept_level = float(np.mean(np.abs(kept.samples[settled])))
    rejected_level = float(np.mean(np.abs(rejected.samples[settled])))

    assert kept_level == pytest.approx(1.0, abs=0.15)
    assert 20.0 * np.log10(rejected_level / max(kept_level, 1e-12)) < -35.0


def test_channelize_streams_blocks_without_discontinuity() -> None:
    channel = ChannelSpec(CENTER_HZ + 120_000.0, 200_000.0)
    plan = plan_channelizer(channel.bandwidth_hz, SAMPLE_RATE_HZ, TARGET_RATE_HZ)
    whole = make_tone(120_000.0, 8192)

    single, _ = channelize(whole, channel, CENTER_HZ, SAMPLE_RATE_HZ, plan)

    chunks = []
    state: ChannelizerState | None = None
    for start in range(0, whole.size, 1000):
        block, state = channelize(
            whole[start : start + 1000], channel, CENTER_HZ, SAMPLE_RATE_HZ, plan, state=state
        )
        chunks.append(block.samples)
    streamed = np.concatenate(chunks)

    assert streamed.size == single.samples.size
    np.testing.assert_allclose(streamed, single.samples, atol=1e-3)
