"""Persisted application settings."""

from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass, fields

from sdr_console.config.defaults import AppDefaults
from sdr_console.dsp.channel import MIN_CHANNEL_BANDWIDTH_HZ
from sdr_console.hal.registry import MOCK_DEVICE_ID, is_known_device_id

CONFIG_VERSION = 3
DEFAULT_DEVICE_ID = MOCK_DEVICE_ID

logger = logging.getLogger(__name__)


@dataclass(eq=True)
class AppConfig:
    """User-facing settings persisted between sessions."""

    config_version: int = CONFIG_VERSION
    device_id: str = DEFAULT_DEVICE_ID
    center_freq_hz: float = 100_000_000.0
    gain_db: float = 20.0
    sample_rate_hz: float = 2_048_000.0
    fft_size: int = 1024
    display_vmin_db: float = -80.0
    display_vmax_db: float = 0.0
    display_colormap: str = "viridis"
    display_refresh_ms: int = 33
    waterfall_history_rows: int = 200
    spectrum_plot_height: int = 180
    device_uri: str = ""
    gain_mode: str = "manual"
    rx_buffer_size: int = 16_384
    listen_freq_hz: float = 100_000_000.0
    channel_bandwidth_hz: float = 200_000.0
    demod_mode: str = "AM"
    audio_volume: float = 0.5
    freq_step_hz: float = 100_000.0
    gain_step_db: float = 1.0

    @classmethod
    def default(cls) -> AppConfig:
        """Build config from built-in application defaults."""
        defaults = AppDefaults()
        return cls(
            center_freq_hz=defaults.center_freq_hz,
            gain_db=defaults.gain_db,
            sample_rate_hz=defaults.sample_rate_hz,
            fft_size=defaults.fft_size,
            display_vmin_db=defaults.display_vmin_db,
            display_vmax_db=defaults.display_vmax_db,
            display_colormap=defaults.display_colormap,
            display_refresh_ms=defaults.display_refresh_ms,
            waterfall_history_rows=defaults.waterfall_history_rows,
            spectrum_plot_height=defaults.spectrum_plot_height,
            device_uri=defaults.device_uri,
            gain_mode=defaults.gain_mode,
            rx_buffer_size=defaults.rx_buffer_size,
            listen_freq_hz=defaults.center_freq_hz,
        )

    def to_defaults(self) -> AppDefaults:
        """Map persisted fields onto runtime ``AppDefaults``."""
        defaults = AppDefaults()
        return AppDefaults(
            sample_rate_hz=self.sample_rate_hz,
            fft_size=self.fft_size,
            center_freq_hz=self.center_freq_hz,
            gain_db=self.gain_db,
            mock_noise_amplitude=defaults.mock_noise_amplitude,
            waterfall_history_rows=self.waterfall_history_rows,
            display_vmin_db=self.display_vmin_db,
            display_vmax_db=self.display_vmax_db,
            display_colormap=self.display_colormap,
            display_refresh_ms=self.display_refresh_ms,
            spectrum_plot_height=self.spectrum_plot_height,
            queue_maxsize=defaults.queue_maxsize,
            raw_queue_maxsize=defaults.raw_queue_maxsize,
            device_uri=self.device_uri,
            gain_mode=self.gain_mode,
            rx_buffer_size=self.rx_buffer_size,
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> AppConfig:
        """Merge ``data`` onto defaults with type/range validation."""
        version_raw = data.get("config_version", CONFIG_VERSION)
        try:
            version = int(version_raw)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            version = CONFIG_VERSION

        payload = dict(data)
        if version != CONFIG_VERSION:
            payload = _migrate(payload, from_version=version)

        base = cls.default()
        allowed = {field.name for field in fields(cls)}
        updates: dict[str, object] = {}

        for key in payload:
            if key not in allowed:
                continue
            try:
                updates[key] = _coerce_field(key, payload[key])
            except (TypeError, ValueError) as exc:
                logger.warning("Ignoring invalid config field %s: %s", key, exc)

        merged = cls(**{**base.to_dict(), **updates})
        return _sanitize(merged)


def _coerce_field(name: str, value: object) -> object:
    if name in {
        "center_freq_hz",
        "gain_db",
        "sample_rate_hz",
        "display_vmin_db",
        "display_vmax_db",
        "listen_freq_hz",
        "channel_bandwidth_hz",
        "audio_volume",
        "freq_step_hz",
        "gain_step_db",
    }:
        return float(value)  # type: ignore[arg-type]
    if name in {
        "fft_size",
        "display_refresh_ms",
        "waterfall_history_rows",
        "spectrum_plot_height",
        "config_version",
        "rx_buffer_size",
    }:
        return int(value)  # type: ignore[arg-type]
    if name in {
        "device_id",
        "display_colormap",
        "device_uri",
        "gain_mode",
        "demod_mode",
    }:
        return str(value)
    return value


def _is_power_of_two(value: int) -> bool:
    return value > 0 and (value & (value - 1)) == 0


def _sanitize(config: AppConfig) -> AppConfig:
    if not is_known_device_id(config.device_id):
        logger.warning(
            "Unknown device_id %r; falling back to %s",
            config.device_id,
            DEFAULT_DEVICE_ID,
        )
        config.device_id = DEFAULT_DEVICE_ID

    if not _is_power_of_two(config.fft_size):
        logger.warning("fft_size %s is not a power of two; using default", config.fft_size)
        config.fft_size = AppConfig.default().fft_size

    if config.display_vmin_db >= config.display_vmax_db:
        logger.warning("display_vmin_db >= display_vmax_db; resetting display levels")
        defaults = AppConfig.default()
        config.display_vmin_db = defaults.display_vmin_db
        config.display_vmax_db = defaults.display_vmax_db

    if config.display_refresh_ms <= 0:
        config.display_refresh_ms = AppConfig.default().display_refresh_ms

    if config.waterfall_history_rows <= 0:
        config.waterfall_history_rows = AppConfig.default().waterfall_history_rows

    if not math.isfinite(config.center_freq_hz):
        config.center_freq_hz = AppConfig.default().center_freq_hz

    if not config.gain_mode:
        config.gain_mode = "manual"

    if config.rx_buffer_size <= 0:
        config.rx_buffer_size = AppConfig.default().rx_buffer_size

    if not math.isfinite(config.listen_freq_hz):
        config.listen_freq_hz = config.center_freq_hz

    if (
        not math.isfinite(config.channel_bandwidth_hz)
        or config.channel_bandwidth_hz < MIN_CHANNEL_BANDWIDTH_HZ
    ):
        logger.warning(
            "channel_bandwidth_hz %s is out of range; using default",
            config.channel_bandwidth_hz,
        )
        config.channel_bandwidth_hz = AppConfig.default().channel_bandwidth_hz

    if not config.demod_mode:
        config.demod_mode = AppConfig.default().demod_mode

    if not math.isfinite(config.audio_volume):
        config.audio_volume = AppConfig.default().audio_volume
    config.audio_volume = min(max(config.audio_volume, 0.0), 1.0)

    if not math.isfinite(config.freq_step_hz) or config.freq_step_hz <= 0.0:
        config.freq_step_hz = AppConfig.default().freq_step_hz

    if not math.isfinite(config.gain_step_db) or config.gain_step_db <= 0.0:
        config.gain_step_db = AppConfig.default().gain_step_db

    return config


def _migrate(data: dict[str, object], from_version: int) -> dict[str, object]:
    """Migrate older config payloads toward ``CONFIG_VERSION``."""
    logger.info("Migrating config from version %s to %s", from_version, CONFIG_VERSION)
    payload = dict(data)
    if from_version < 2:
        payload.setdefault("device_uri", "")
        payload.setdefault("gain_mode", "manual")
        payload.setdefault("rx_buffer_size", 16_384)
    if from_version < 3:
        payload.setdefault("listen_freq_hz", payload.get("center_freq_hz", 100_000_000.0))
        payload.setdefault("channel_bandwidth_hz", 200_000.0)
        payload.setdefault("demod_mode", "AM")
        payload.setdefault("audio_volume", 0.5)
        payload.setdefault("freq_step_hz", 100_000.0)
        payload.setdefault("gain_step_db", 1.0)
    payload["config_version"] = CONFIG_VERSION
    return payload
