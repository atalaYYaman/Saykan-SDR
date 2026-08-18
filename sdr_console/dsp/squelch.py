"""Channel (IF) power squelch with hysteresis and hang time.

Applied after channelisation and before demodulation decisions: measures mean
power of the complex IF block and gates audio open/closed. Pure stateful
logic — no demodulator or UI dependency.
"""

from __future__ import annotations

import math

import numpy as np

# Practical UI / config bounds (dBFS relative to |IQ| = 1).
MIN_SQUELCH_THRESHOLD_DB = -120.0
MAX_SQUELCH_THRESHOLD_DB = 0.0
DEFAULT_SQUELCH_THRESHOLD_DB = -50.0
DEFAULT_SQUELCH_HYSTERESIS_DB = 3.0
DEFAULT_SQUELCH_HANG_S = 0.15


def channel_power_db(samples: np.ndarray) -> float:
    """Mean power of complex (or real) samples in dB relative to amplitude 1.

    Empty input returns ``-inf``.
    """
    if samples.size == 0:
        return float("-inf")
    power = float(np.mean(np.square(np.abs(samples), dtype=np.float64)))
    if power <= 0.0:
        return float("-inf")
    return 10.0 * math.log10(power)


class ChannelSquelch:
    """Open/close gate driven by IF power with hysteresis and hang."""

    def __init__(
        self,
        open_threshold_db: float = DEFAULT_SQUELCH_THRESHOLD_DB,
        hysteresis_db: float = DEFAULT_SQUELCH_HYSTERESIS_DB,
        hang_s: float = DEFAULT_SQUELCH_HANG_S,
        *,
        enabled: bool = True,
    ) -> None:
        if hysteresis_db < 0.0:
            raise ValueError("hysteresis_db must be non-negative")
        if hang_s < 0.0:
            raise ValueError("hang_s must be non-negative")

        self._enabled = bool(enabled)
        self._open_threshold_db = float(open_threshold_db)
        self._hysteresis_db = float(hysteresis_db)
        self._hang_s = float(hang_s)
        self._open = False
        self._hang_left_s = 0.0

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def open_threshold_db(self) -> float:
        return self._open_threshold_db

    @property
    def close_threshold_db(self) -> float:
        return self._open_threshold_db - self._hysteresis_db

    @property
    def hysteresis_db(self) -> float:
        return self._hysteresis_db

    @property
    def hang_s(self) -> float:
        return self._hang_s

    @property
    def is_open(self) -> bool:
        """Whether the gate is currently open (audio unmuted)."""
        return (not self._enabled) or self._open

    def configure(
        self,
        *,
        open_threshold_db: float | None = None,
        hysteresis_db: float | None = None,
        hang_s: float | None = None,
        enabled: bool | None = None,
    ) -> None:
        """Update parameters without resetting open/hang state unless disabling."""
        if open_threshold_db is not None:
            self._open_threshold_db = float(open_threshold_db)
        if hysteresis_db is not None:
            if hysteresis_db < 0.0:
                raise ValueError("hysteresis_db must be non-negative")
            self._hysteresis_db = float(hysteresis_db)
        if hang_s is not None:
            if hang_s < 0.0:
                raise ValueError("hang_s must be non-negative")
            self._hang_s = float(hang_s)
        if enabled is not None:
            self._enabled = bool(enabled)
            if not self._enabled:
                self._open = False
                self._hang_left_s = 0.0

    def reset(self) -> None:
        self._open = False
        self._hang_left_s = 0.0

    def update(self, power_db: float, block_duration_s: float) -> bool:
        """Feed one block's IF power; return whether audio should pass.

        Args:
            power_db: Channel power from :func:`channel_power_db`.
            block_duration_s: Duration of the IF block in seconds (for hang).
        """
        if not self._enabled:
            return True
        if block_duration_s < 0.0:
            raise ValueError("block_duration_s must be non-negative")

        if not self._open:
            if power_db >= self._open_threshold_db:
                self._open = True
                self._hang_left_s = self._hang_s
            return self._open

        # Currently open.
        if power_db >= self.close_threshold_db:
            self._hang_left_s = self._hang_s
            return True

        # Below close threshold: consume hang time, then close.
        if self._hang_left_s <= block_duration_s:
            self._hang_left_s = 0.0
            self._open = False
            return False
        self._hang_left_s -= block_duration_s
        return True
