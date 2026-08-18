"""Audio AGC — fast / slow / hang / limiter profiles.

Pure stateful processor. Applied after AFBW and before the final soft-limit /
clip. Envelope is a one-pole follower with separate attack and decay; hang
holds the peak estimate before decay begins.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

import numpy as np


class AgcPreset(str, Enum):
    """Named timing / gain profiles selectable from the UI."""

    FAST = "fast"
    SLOW = "slow"
    HANG = "hang"
    LIMITER = "limiter"


AGC_PRESET_CHOICES: tuple[AgcPreset, ...] = tuple(AgcPreset)


@dataclass(frozen=True)
class AgcProfile:
    """Timing and level parameters for one AGC preset."""

    attack_s: float
    decay_s: float
    hang_s: float
    threshold: float
    target: float
    max_gain: float


# Speech: chase peaks quickly, recover at a moderate rate.
PROFILE_FAST = AgcProfile(
    attack_s=0.005,
    decay_s=0.150,
    hang_s=0.0,
    threshold=0.02,
    target=0.30,
    max_gain=40.0,
)
# Broadcast AM: slower, smoother level.
PROFILE_SLOW = AgcProfile(
    attack_s=0.050,
    decay_s=0.600,
    hang_s=0.0,
    threshold=0.02,
    target=0.30,
    max_gain=40.0,
)
# SSB with hang: hold after a syllable before pumping up noise.
PROFILE_HANG = AgcProfile(
    attack_s=0.005,
    decay_s=0.500,
    hang_s=0.250,
    threshold=0.02,
    target=0.30,
    max_gain=40.0,
)
# FM: mostly peak limiting — little boost of quiet noise.
PROFILE_LIMITER = AgcProfile(
    attack_s=0.002,
    decay_s=0.080,
    hang_s=0.0,
    threshold=0.25,
    target=0.70,
    max_gain=4.0,
)

AGC_PROFILES: dict[AgcPreset, AgcProfile] = {
    AgcPreset.FAST: PROFILE_FAST,
    AgcPreset.SLOW: PROFILE_SLOW,
    AgcPreset.HANG: PROFILE_HANG,
    AgcPreset.LIMITER: PROFILE_LIMITER,
}


def _coeff(time_s: float, sample_rate_hz: float) -> float:
    """One-pole coefficient ``1 - exp(-1/(τ·fs))``; 1.0 means instant."""
    if time_s <= 0.0:
        return 1.0
    return float(1.0 - math.exp(-1.0 / (time_s * sample_rate_hz)))


class AutomaticGainControl:
    """Sample-wise AGC with attack, decay, optional hang, and max gain."""

    def __init__(
        self,
        sample_rate_hz: float,
        profile: AgcProfile,
        *,
        enabled: bool = True,
    ) -> None:
        if sample_rate_hz <= 0.0:
            raise ValueError("sample_rate_hz must be positive")
        if profile.attack_s < 0.0 or profile.decay_s < 0.0 or profile.hang_s < 0.0:
            raise ValueError("AGC times must be non-negative")
        if profile.threshold <= 0.0 or profile.target <= 0.0 or profile.max_gain <= 0.0:
            raise ValueError("threshold, target and max_gain must be positive")

        self._sample_rate_hz = float(sample_rate_hz)
        self._profile = profile
        self._enabled = bool(enabled)
        self._attack = _coeff(profile.attack_s, sample_rate_hz)
        self._decay = _coeff(profile.decay_s, sample_rate_hz)
        self._hang_samples = int(round(profile.hang_s * sample_rate_hz))
        self._threshold = float(profile.threshold)
        self._target = float(profile.target)
        self._max_gain = float(profile.max_gain)

        self._level = self._threshold
        self._hang_left = 0
        self._gain = 1.0

    @classmethod
    def from_preset(
        cls,
        sample_rate_hz: float,
        preset: AgcPreset | str,
        *,
        enabled: bool = True,
    ) -> AutomaticGainControl:
        key = AgcPreset(preset)
        return cls(sample_rate_hz, AGC_PROFILES[key], enabled=enabled)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def sample_rate_hz(self) -> float:
        return self._sample_rate_hz

    @property
    def profile(self) -> AgcProfile:
        return self._profile

    @property
    def gain(self) -> float:
        """Most recent gain applied (after the last ``process`` call)."""
        return self._gain

    @property
    def level(self) -> float:
        """Smoothed envelope estimate."""
        return self._level

    def reset(self) -> None:
        self._level = self._threshold
        self._hang_left = 0
        self._gain = 1.0

    def process(self, samples: np.ndarray) -> np.ndarray:
        """Apply AGC to one float audio block; returns float64."""
        x = np.asarray(samples, dtype=np.float64)
        if x.size == 0:
            return x.copy()
        if not self._enabled:
            return x.copy()

        out = np.empty(x.size, dtype=np.float64)
        level = self._level
        hang_left = self._hang_left
        attack = self._attack
        decay = self._decay
        hang_samples = self._hang_samples
        threshold = self._threshold
        target = self._target
        max_gain = self._max_gain
        gain = self._gain

        for i in range(x.size):
            env = abs(x[i])
            if env > level:
                level += (env - level) * attack
                hang_left = hang_samples
            elif hang_left > 0:
                hang_left -= 1
            else:
                level += (env - level) * decay

            denom = level if level > threshold else threshold
            desired = target / denom
            if desired > max_gain:
                desired = max_gain
            gain = desired
            out[i] = x[i] * gain

        self._level = level
        self._hang_left = hang_left
        self._gain = gain
        return out
