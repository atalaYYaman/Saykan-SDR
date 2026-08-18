"""Unit tests for continuous vs discrete DeviceCapabilities."""

import pytest

from sdr_console.hal.capabilities import DeviceCapabilities


def test_discrete_sample_rate_membership() -> None:
    caps = DeviceCapabilities(
        min_freq_hz=1.0,
        max_freq_hz=2.0,
        supported_sample_rates_hz=(1_000_000.0, 2_000_000.0),
        min_gain_db=0.0,
        max_gain_db=10.0,
    )
    assert not caps.has_continuous_sample_rates
    caps.validate_sample_rate_hz(1_000_000.0)
    with pytest.raises(ValueError):
        caps.validate_sample_rate_hz(1_500_000.0)


def test_continuous_sample_rate_range() -> None:
    caps = DeviceCapabilities(
        min_freq_hz=70e6,
        max_freq_hz=6e9,
        supported_sample_rates_hz=(1e6, 2.048e6),
        min_gain_db=-3.0,
        max_gain_db=71.0,
        min_sample_rate_hz=521_000.0,
        max_sample_rate_hz=61_440_000.0,
    )
    assert caps.has_continuous_sample_rates
    caps.validate_sample_rate_hz(3_000_000.0)
    with pytest.raises(ValueError):
        caps.validate_sample_rate_hz(100_000.0)
    with pytest.raises(ValueError):
        caps.validate_sample_rate_hz(100_000_000.0)


def test_validate_gain_mode() -> None:
    caps = DeviceCapabilities(
        min_freq_hz=1.0,
        max_freq_hz=2.0,
        supported_sample_rates_hz=(1e6,),
        min_gain_db=0.0,
        max_gain_db=10.0,
        gain_modes=("manual", "slow_attack"),
    )
    caps.validate_gain_mode("manual")
    with pytest.raises(ValueError):
        caps.validate_gain_mode("bogus")


def test_clamp_gain_and_freq_to_edges() -> None:
    caps = DeviceCapabilities(
        min_freq_hz=70e6,
        max_freq_hz=6e9,
        supported_sample_rates_hz=(1e6,),
        min_gain_db=-3.0,
        max_gain_db=71.0,
    )
    assert caps.clamp_gain_db(73.0) == 71.0
    assert caps.clamp_gain_db(-10.0) == -3.0
    assert caps.clamp_freq_hz(10e6) == 70e6
    assert caps.clamp_freq_hz(7e9) == 6e9


def test_clamp_discrete_sample_rate_picks_nearest() -> None:
    caps = DeviceCapabilities(
        min_freq_hz=1.0,
        max_freq_hz=2.0,
        supported_sample_rates_hz=(2_048_000.0, 2_400_000.0, 2_560_000.0),
        min_gain_db=0.0,
        max_gain_db=50.0,
    )
    assert caps.clamp_sample_rate_hz(2_500_000.0) == 2_560_000.0
    assert caps.clamp_sample_rate_hz(2_048_000.0) == 2_048_000.0


def test_clamp_continuous_sample_rate_to_range() -> None:
    caps = DeviceCapabilities(
        min_freq_hz=70e6,
        max_freq_hz=6e9,
        supported_sample_rates_hz=(1e6, 2.048e6),
        min_gain_db=-3.0,
        max_gain_db=71.0,
        min_sample_rate_hz=521_000.0,
        max_sample_rate_hz=61_440_000.0,
    )
    assert caps.clamp_sample_rate_hz(2_500_000.0) == 2_500_000.0
    assert caps.clamp_sample_rate_hz(100_000.0) == 521_000.0


def test_clamp_gain_mode_falls_back() -> None:
    caps = DeviceCapabilities(
        min_freq_hz=1.0,
        max_freq_hz=2.0,
        supported_sample_rates_hz=(1e6,),
        min_gain_db=0.0,
        max_gain_db=10.0,
        gain_modes=("manual", "slow_attack"),
    )
    assert caps.clamp_gain_mode("slow_attack") == "slow_attack"
    assert caps.clamp_gain_mode("bogus") == "manual"
