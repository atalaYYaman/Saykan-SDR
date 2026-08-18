"""Unit tests for audio AGC (ADIM A5)."""

from __future__ import annotations

import numpy as np
import pytest

from sdr_console.demod.am import AMDemodulator
from sdr_console.demod.cw import CWDemodulator
from sdr_console.demod.factory import (
    default_agc_enabled,
    default_agc_preset,
)
from sdr_console.demod.fm import NFMDemodulator, WFMDemodulator
from sdr_console.demod.ssb import USBDemodulator
from sdr_console.dsp.agc import (
    PROFILE_FAST,
    PROFILE_HANG,
    PROFILE_LIMITER,
    PROFILE_SLOW,
    AgcPreset,
    AutomaticGainControl,
)


def tone(amplitude: float, sample_rate_hz: float, duration_s: float, freq_hz: float = 1_000.0) -> np.ndarray:
    n = int(sample_rate_hz * duration_s)
    t = np.arange(n, dtype=np.float64) / sample_rate_hz
    return amplitude * np.sin(2.0 * np.pi * freq_hz * t)


def test_agc_normalises_varying_envelope_to_target() -> None:
    sample_rate_hz = 48_000.0
    agc = AutomaticGainControl.from_preset(sample_rate_hz, AgcPreset.FAST)
    # Quiet then loud then a long quiet recovery.
    quiet = tone(0.05, sample_rate_hz, 0.5)
    loud = tone(0.80, sample_rate_hz, 0.4)
    recovery = tone(0.05, sample_rate_hz, 1.0)
    mixed = np.concatenate([quiet, loud, recovery])
    out = agc.process(mixed)

    def segment_peak(start_s: float, end_s: float) -> float:
        start = int(start_s * sample_rate_hz)
        end = int(end_s * sample_rate_hz)
        settle = start + (end - start) // 2
        return float(np.percentile(np.abs(out[settle:end]), 95))

    quiet1 = segment_peak(0.20, 0.45)
    loud_seg = segment_peak(0.60, 0.85)
    quiet2 = segment_peak(1.40, 1.80)
    target = PROFILE_FAST.target

    assert quiet1 == pytest.approx(target, rel=0.35)
    assert loud_seg == pytest.approx(target, rel=0.35)
    assert quiet2 == pytest.approx(target, rel=0.35)
    assert max(quiet1, loud_seg) / min(quiet1, loud_seg) < 1.6


def test_agc_attack_is_faster_than_decay() -> None:
    sample_rate_hz = 48_000.0
    agc = AutomaticGainControl(sample_rate_hz, PROFILE_SLOW)
    # Establish on a mid-level tone, then jump loud and measure gain drop time.
    warm = tone(0.2, sample_rate_hz, 0.5)
    agc.process(warm)
    gain_before = agc.gain

    loud = tone(0.9, sample_rate_hz, 0.05)
    agc.process(loud)
    gain_after_attack = agc.gain
    assert gain_after_attack < gain_before * 0.5

    # After a short quiet gap, slow decay should not have fully recovered yet.
    quiet = tone(0.05, sample_rate_hz, PROFILE_SLOW.decay_s * 0.2)
    agc.process(quiet)
    gain_mid_decay = agc.gain
    assert gain_mid_decay < gain_before


def test_agc_hang_holds_gain_before_decay() -> None:
    sample_rate_hz = 48_000.0
    agc = AutomaticGainControl(sample_rate_hz, PROFILE_HANG)
    agc.process(tone(0.8, sample_rate_hz, 0.2))
    gain_after_peak = agc.gain

    # During hang, a quiet input should not raise gain yet.
    hang_block = tone(0.02, sample_rate_hz, PROFILE_HANG.hang_s * 0.5)
    agc.process(hang_block)
    assert agc.gain == pytest.approx(gain_after_peak, rel=0.05)

    # After hang expires and decay runs, gain should rise.
    agc.process(tone(0.02, sample_rate_hz, PROFILE_HANG.hang_s + PROFILE_HANG.decay_s))
    assert agc.gain > gain_after_peak * 1.5


def test_agc_disabled_is_passthrough() -> None:
    sample_rate_hz = 48_000.0
    agc = AutomaticGainControl.from_preset(
        sample_rate_hz, AgcPreset.FAST, enabled=False
    )
    x = tone(0.1, sample_rate_hz, 0.05)
    np.testing.assert_allclose(agc.process(x), x)


def test_limiter_profile_has_low_max_gain() -> None:
    assert PROFILE_LIMITER.max_gain <= 4.0
    assert PROFILE_LIMITER.threshold > PROFILE_FAST.threshold


@pytest.mark.parametrize(
    ("mode", "enabled", "preset"),
    [
        ("AM", True, "slow"),
        ("USB", True, "hang"),
        ("LSB", True, "hang"),
        ("CW", True, "fast"),
        ("N-FM", True, "limiter"),
        ("W-FM", True, "limiter"),
    ],
)
def test_mode_default_agc(mode: str, enabled: bool, preset: str) -> None:
    assert default_agc_enabled(mode) is enabled
    assert default_agc_preset(mode) == preset


@pytest.mark.parametrize(
    ("cls", "preset"),
    [
        (AMDemodulator, AgcPreset.SLOW),
        (USBDemodulator, AgcPreset.HANG),
        (CWDemodulator, AgcPreset.FAST),
        (NFMDemodulator, AgcPreset.LIMITER),
        (WFMDemodulator, AgcPreset.LIMITER),
    ],
)
def test_demodulators_default_agc_preset(cls, preset: AgcPreset) -> None:
    rate = 48_000.0 if cls is not WFMDemodulator else 240_000.0
    decimation = 1 if cls is not WFMDemodulator else 5
    demod = cls(input_rate_hz=rate, audio_decimation=decimation)
    assert demod.agc_enabled is True
    assert demod.agc_preset == preset
