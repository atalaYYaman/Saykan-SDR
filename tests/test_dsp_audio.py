"""Unit tests for audio-rate DSP primitives."""

from __future__ import annotations

import numpy as np
import pytest

from sdr_console.dsp.audio import (
    apply_iir,
    choose_total_decimation,
    clip_audio,
    design_dc_blocker,
    is_smooth,
    plan_audio_decimation,
    plan_demod_chain,
    soft_limit_audio,
    split_decimation,
)


def test_plan_audio_decimation_picks_the_closest_integer_rate() -> None:
    plan = plan_audio_decimation(204_800.0, 48_000.0)

    assert plan.decimation == 4
    assert plan.audio_rate_hz == pytest.approx(51_200.0)
    assert plan.num_taps > 1


def test_plan_audio_decimation_passes_through_when_already_at_audio_rate() -> None:
    plan = plan_audio_decimation(48_761.9, 48_000.0)

    assert plan.decimation == 1
    assert plan.audio_rate_hz == pytest.approx(48_761.9)
    assert plan.num_taps == 1


def test_plan_audio_decimation_filter_protects_the_new_nyquist() -> None:
    plan = plan_audio_decimation(204_800.0, 48_000.0)
    response = np.fft.rfft(plan.taps, n=8192)
    freqs = np.fft.rfftfreq(8192, d=1.0 / 204_800.0)
    magnitude_db = 20.0 * np.log10(np.maximum(np.abs(response), 1e-12))

    passband = magnitude_db[freqs <= 0.4 * plan.audio_rate_hz]
    stopband = magnitude_db[freqs >= 0.6 * plan.audio_rate_hz]

    assert np.all(passband > -1.5)
    assert np.all(stopband < -40.0)


@pytest.mark.parametrize("bad_value", [0.0, -5.0])
def test_plan_audio_decimation_rejects_non_positive_rates(bad_value: float) -> None:
    with pytest.raises(ValueError):
        plan_audio_decimation(bad_value, 48_000.0)
    with pytest.raises(ValueError):
        plan_audio_decimation(48_000.0, bad_value)


def test_plan_audio_decimation_accepts_a_forced_factor() -> None:
    plan = plan_audio_decimation(204_800.0, 48_000.0, decimation=8)

    assert plan.decimation == 8
    assert plan.audio_rate_hz == pytest.approx(25_600.0)


@pytest.mark.parametrize(
    ("total", "max_first", "expected"),
    [
        (42, 10, (7, 6)),
        (42, 5, (3, 14)),
        (42, 100, (42, 1)),
        (42, 1, (1, 42)),
        (1, 8, (1, 1)),
        (49, 6, (1, 49)),
    ],
)
def test_split_decimation_takes_the_largest_allowed_divisor(
    total: int,
    max_first: int,
    expected: tuple[int, int],
) -> None:
    first, second = split_decimation(total, max_first)

    assert (first, second) == expected
    assert first * second == total


@pytest.mark.parametrize(("total", "max_first"), [(0, 4), (4, 0)])
def test_split_decimation_rejects_non_positive_arguments(
    total: int,
    max_first: int,
) -> None:
    with pytest.raises(ValueError):
        split_decimation(total, max_first)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(42, True), (43, False), (1, True), (49, True), (44, False), (0, False)],
)
def test_is_smooth_accepts_only_small_prime_factors(value: int, expected: bool) -> None:
    assert is_smooth(value) is expected


def test_choose_total_decimation_prefers_a_factor_rich_number() -> None:
    # 2.048 Msps / 48 kHz is 42.67 and 43 is prime, which would leave nothing to
    # split between the two stages.
    assert choose_total_decimation(2_048_000.0, 48_000.0) == 42
    assert choose_total_decimation(2_400_000.0, 48_000.0) == 50
    assert choose_total_decimation(250_000.0, 48_000.0) == 5


def test_choose_total_decimation_stays_within_tolerance() -> None:
    total = choose_total_decimation(2_048_000.0, 48_000.0)
    audio_rate_hz = 2_048_000.0 / total

    assert abs(audio_rate_hz - 48_000.0) / 48_000.0 < 0.2


def test_choose_total_decimation_is_one_below_the_audio_rate() -> None:
    assert choose_total_decimation(32_000.0, 48_000.0) == 1


@pytest.mark.parametrize("bandwidth_hz", [10_000.0, 125_000.0, 200_000.0, 350_000.0])
def test_plan_demod_chain_keeps_the_audio_rate_constant(bandwidth_hz: float) -> None:
    plan = plan_demod_chain(2_048_000.0, bandwidth_hz, 48_000.0)

    # Constant audio rate is what lets the sound card stay open while the user
    # changes bandwidth.
    assert plan.audio_rate_hz == pytest.approx(2_048_000.0 / 42)
    assert plan.total_decimation == 42
    # The IF stage must still leave room for the requested bandwidth.
    assert plan.if_rate_hz >= bandwidth_hz


def test_plan_demod_chain_gives_the_channel_stage_as_much_as_it_can() -> None:
    narrow = plan_demod_chain(2_048_000.0, 10_000.0, 48_000.0)
    wide = plan_demod_chain(2_048_000.0, 350_000.0, 48_000.0)

    assert narrow.channel.decimation == 42
    assert narrow.audio_decimation == 1
    assert wide.channel.decimation < narrow.channel.decimation
    assert wide.audio_decimation > narrow.audio_decimation


@pytest.mark.parametrize(
    ("sample_rate_hz", "bandwidth_hz", "audio_rate_hz"),
    [(0.0, 10_000.0, 48_000.0), (2_048_000.0, 0.0, 48_000.0), (2_048_000.0, 1e4, 0.0)],
)
def test_plan_demod_chain_rejects_non_positive_arguments(
    sample_rate_hz: float,
    bandwidth_hz: float,
    audio_rate_hz: float,
) -> None:
    with pytest.raises(ValueError):
        plan_demod_chain(sample_rate_hz, bandwidth_hz, audio_rate_hz)


def test_dc_blocker_removes_a_constant_but_keeps_a_tone() -> None:
    sample_rate_hz = 48_000.0
    b, a = design_dc_blocker(sample_rate_hz, cutoff_hz=30.0)
    time_s = np.arange(48_000, dtype=np.float64) / sample_rate_hz
    tone = np.sin(2.0 * np.pi * 1_000.0 * time_s)

    filtered, _ = apply_iir(tone + 5.0, b, a)
    settled = filtered[8_000:]

    assert abs(float(np.mean(settled))) < 0.01
    assert float(np.max(np.abs(settled))) == pytest.approx(1.0, abs=0.02)


def test_apply_iir_state_makes_block_processing_identical() -> None:
    b, a = design_dc_blocker(48_000.0)
    samples = np.linspace(0.0, 1.0, 1_000, dtype=np.float64) + 2.0

    whole, _ = apply_iir(samples, b, a)
    first, state = apply_iir(samples[:400], b, a)
    second, _ = apply_iir(samples[400:], b, a, state)

    np.testing.assert_allclose(np.concatenate([first, second]), whole, atol=1e-12)


@pytest.mark.parametrize("bad_value", [0.0, -1.0])
def test_design_dc_blocker_rejects_invalid_arguments(bad_value: float) -> None:
    with pytest.raises(ValueError):
        design_dc_blocker(bad_value)
    with pytest.raises(ValueError):
        design_dc_blocker(48_000.0, cutoff_hz=bad_value)


def test_apply_iir_requires_at_least_first_order() -> None:
    with pytest.raises(ValueError):
        apply_iir(
            np.zeros(4),
            np.array([1.0]),
            np.array([1.0]),
        )


def test_clip_audio_limits_the_range_and_returns_float32() -> None:
    clipped = clip_audio(np.array([-3.0, -0.5, 0.25, 2.0]))

    assert clipped.dtype == np.float32
    np.testing.assert_allclose(clipped, np.array([-1.0, -0.5, 0.25, 1.0], dtype=np.float32))


def test_soft_limit_audio_is_exported_from_dsp_package() -> None:
    from sdr_console.dsp import soft_limit_audio as exported

    assert exported is soft_limit_audio
