"""Unit tests for audio-rate DSP primitives."""

from __future__ import annotations

import numpy as np
import pytest

from sdr_console.dsp.audio import (
    apply_iir,
    clip_audio,
    design_dc_blocker,
    plan_audio_decimation,
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
