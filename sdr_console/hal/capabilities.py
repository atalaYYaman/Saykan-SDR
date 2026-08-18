"""Hardware capability descriptors shared across SDR drivers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceCapabilities:
    """Describes the tunable ranges and discrete options of an SDR device.

    Sample-rate validation has two modes:

    * **Discrete** (default): ``min_sample_rate_hz`` / ``max_sample_rate_hz``
      are ``None`` and ``supported_sample_rates_hz`` is the exact allowed set.
    * **Continuous**: both min and max are set; ``supported_sample_rates_hz``
      is then a UI preset list only, and any rate inside ``[min, max]`` is valid.
    """

    min_freq_hz: float
    max_freq_hz: float
    supported_sample_rates_hz: tuple[float, ...]
    min_gain_db: float
    max_gain_db: float
    min_sample_rate_hz: float | None = None
    max_sample_rate_hz: float | None = None
    gain_modes: tuple[str, ...] = ("manual",)

    @property
    def has_continuous_sample_rates(self) -> bool:
        """Return True when sample rates are validated as a continuous range."""
        return self.min_sample_rate_hz is not None and self.max_sample_rate_hz is not None

    def validate_freq_hz(self, freq_hz: float) -> None:
        """Raise ValueError when ``freq_hz`` is outside the device range."""
        if not self.min_freq_hz <= freq_hz <= self.max_freq_hz:
            raise ValueError(
                f"Frequency {freq_hz} Hz out of range "
                f"[{self.min_freq_hz}, {self.max_freq_hz}]"
            )

    def validate_sample_rate_hz(self, rate_hz: float) -> None:
        """Raise ValueError when ``rate_hz`` is not supported."""
        if self.has_continuous_sample_rates:
            assert self.min_sample_rate_hz is not None
            assert self.max_sample_rate_hz is not None
            if not self.min_sample_rate_hz <= rate_hz <= self.max_sample_rate_hz:
                raise ValueError(
                    f"Sample rate {rate_hz} Hz out of range "
                    f"[{self.min_sample_rate_hz}, {self.max_sample_rate_hz}]"
                )
            return

        if rate_hz not in self.supported_sample_rates_hz:
            supported = ", ".join(f"{r:g}" for r in self.supported_sample_rates_hz)
            raise ValueError(
                f"Sample rate {rate_hz} Hz not supported; choose one of: {supported}"
            )

    def validate_gain_db(self, gain_db: float) -> None:
        """Raise ValueError when ``gain_db`` is outside the device range."""
        if not self.min_gain_db <= gain_db <= self.max_gain_db:
            raise ValueError(
                f"Gain {gain_db} dB out of range "
                f"[{self.min_gain_db}, {self.max_gain_db}]"
            )

    def validate_gain_mode(self, mode: str) -> None:
        """Raise ValueError when ``mode`` is not in ``gain_modes``."""
        if mode not in self.gain_modes:
            allowed = ", ".join(self.gain_modes)
            raise ValueError(f"Gain mode {mode!r} not supported; choose one of: {allowed}")

    def clamp_freq_hz(self, freq_hz: float) -> float:
        """Return ``freq_hz`` limited to ``[min_freq_hz, max_freq_hz]``."""
        return min(max(float(freq_hz), self.min_freq_hz), self.max_freq_hz)

    def clamp_gain_db(self, gain_db: float) -> float:
        """Return ``gain_db`` limited to ``[min_gain_db, max_gain_db]``."""
        return min(max(float(gain_db), self.min_gain_db), self.max_gain_db)

    def clamp_sample_rate_hz(self, rate_hz: float) -> float:
        """Return a valid sample rate closest to ``rate_hz``.

        Continuous devices clamp to ``[min, max]``. Discrete devices pick the
        nearest entry in ``supported_sample_rates_hz``.
        """
        rate = float(rate_hz)
        if self.has_continuous_sample_rates:
            assert self.min_sample_rate_hz is not None
            assert self.max_sample_rate_hz is not None
            return min(max(rate, self.min_sample_rate_hz), self.max_sample_rate_hz)

        if not self.supported_sample_rates_hz:
            return rate
        if rate in self.supported_sample_rates_hz:
            return rate
        return min(self.supported_sample_rates_hz, key=lambda supported: abs(supported - rate))

    def clamp_gain_mode(self, mode: str) -> str:
        """Return ``mode`` if supported, otherwise the first listed gain mode."""
        if mode in self.gain_modes:
            return mode
        return self.gain_modes[0] if self.gain_modes else "manual"
