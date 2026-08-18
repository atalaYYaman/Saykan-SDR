"""Persisted application settings."""

from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass, fields

from sdr_console.config.defaults import AppDefaults
from sdr_console.demod.factory import (
    default_afbw_hz,
    default_agc_enabled,
    default_agc_preset,
    default_bandwidth_hz,
    is_known_demod_mode,
)
from sdr_console.dsp.afbw import MAX_AFBW_HZ, MIN_AFBW_HZ
from sdr_console.dsp.agc import AgcPreset
from sdr_console.dsp.channel import MIN_CHANNEL_BANDWIDTH_HZ
from sdr_console.dsp.squelch import (
    DEFAULT_SQUELCH_HANG_S,
    DEFAULT_SQUELCH_HYSTERESIS_DB,
    DEFAULT_SQUELCH_THRESHOLD_DB,
    MAX_SQUELCH_THRESHOLD_DB,
    MIN_SQUELCH_THRESHOLD_DB,
)
from sdr_console.hal.registry import MOCK_DEVICE_ID, is_known_device_id

CONFIG_VERSION = 5
WINDOW_LAYOUT_VERSION = 5
DEFAULT_DEVICE_ID = MOCK_DEVICE_ID
DEFAULT_DEMOD_MODE = "AM"
DEFAULT_CHANNEL_BANDWIDTH_HZ = default_bandwidth_hz(DEFAULT_DEMOD_MODE)
DEFAULT_AFBW_HZ = default_afbw_hz(DEFAULT_DEMOD_MODE)
DEFAULT_AGC_ENABLED = default_agc_enabled(DEFAULT_DEMOD_MODE)
DEFAULT_AGC_PRESET = default_agc_preset(DEFAULT_DEMOD_MODE)

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
    channel_bandwidth_hz: float = DEFAULT_CHANNEL_BANDWIDTH_HZ
    demod_mode: str = DEFAULT_DEMOD_MODE
    audio_volume: float = 0.5
    deemphasis_tau_us: float = 75.0
    nfm_deemphasis: bool = False
    afbw_hz: float = DEFAULT_AFBW_HZ
    agc_enabled: bool = DEFAULT_AGC_ENABLED
    agc_preset: str = DEFAULT_AGC_PRESET
    squelch_enabled: bool = False
    squelch_threshold_db: float = DEFAULT_SQUELCH_THRESHOLD_DB
    squelch_hysteresis_db: float = DEFAULT_SQUELCH_HYSTERESIS_DB
    squelch_hang_s: float = DEFAULT_SQUELCH_HANG_S
    freq_step_hz: float = 100_000.0
    gain_step_db: float = 1.0
    window_state: str = ""
    window_layout_version: int = WINDOW_LAYOUT_VERSION

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
        "deemphasis_tau_us",
        "afbw_hz",
        "squelch_threshold_db",
        "squelch_hysteresis_db",
        "squelch_hang_s",
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
        "window_layout_version",
    }:
        return int(value)  # type: ignore[arg-type]
    if name in {"nfm_deemphasis", "agc_enabled", "squelch_enabled"}:
        return bool(value)
    if name in {
        "device_id",
        "display_colormap",
        "device_uri",
        "gain_mode",
        "demod_mode",
        "agc_preset",
        "window_state",
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

    if not config.demod_mode or not is_known_demod_mode(config.demod_mode):
        if config.demod_mode and not is_known_demod_mode(config.demod_mode):
            logger.warning(
                "demod_mode %r is unknown; using %s",
                config.demod_mode,
                AppConfig.default().demod_mode,
            )
        config.demod_mode = AppConfig.default().demod_mode

    if not math.isfinite(config.audio_volume):
        config.audio_volume = AppConfig.default().audio_volume
    config.audio_volume = min(max(config.audio_volume, 0.0), 1.0)

    if (
        not math.isfinite(config.deemphasis_tau_us)
        or config.deemphasis_tau_us not in (50.0, 75.0)
    ):
        logger.warning(
            "deemphasis_tau_us %s is invalid; using 75",
            config.deemphasis_tau_us,
        )
        config.deemphasis_tau_us = 75.0

    config.nfm_deemphasis = bool(config.nfm_deemphasis)

    if (
        not math.isfinite(config.afbw_hz)
        or config.afbw_hz < MIN_AFBW_HZ
        or config.afbw_hz > MAX_AFBW_HZ
    ):
        logger.warning("afbw_hz %s is out of range; using default", config.afbw_hz)
        config.afbw_hz = AppConfig.default().afbw_hz

    config.agc_enabled = bool(config.agc_enabled)
    try:
        config.agc_preset = AgcPreset(str(config.agc_preset)).value
    except ValueError:
        logger.warning("agc_preset %r is unknown; using default", config.agc_preset)
        config.agc_preset = AppConfig.default().agc_preset

    config.squelch_enabled = bool(config.squelch_enabled)
    if (
        not math.isfinite(config.squelch_threshold_db)
        or config.squelch_threshold_db < MIN_SQUELCH_THRESHOLD_DB
        or config.squelch_threshold_db > MAX_SQUELCH_THRESHOLD_DB
    ):
        logger.warning(
            "squelch_threshold_db %s is out of range; using default",
            config.squelch_threshold_db,
        )
        config.squelch_threshold_db = DEFAULT_SQUELCH_THRESHOLD_DB

    if (
        not math.isfinite(config.squelch_hysteresis_db)
        or config.squelch_hysteresis_db < 0.0
        or config.squelch_hysteresis_db > 40.0
    ):
        config.squelch_hysteresis_db = DEFAULT_SQUELCH_HYSTERESIS_DB

    if (
        not math.isfinite(config.squelch_hang_s)
        or config.squelch_hang_s < 0.0
        or config.squelch_hang_s > 5.0
    ):
        config.squelch_hang_s = DEFAULT_SQUELCH_HANG_S

    if not math.isfinite(config.freq_step_hz) or config.freq_step_hz <= 0.0:
        config.freq_step_hz = AppConfig.default().freq_step_hz

    if not math.isfinite(config.gain_step_db) or config.gain_step_db <= 0.0:
        config.gain_step_db = AppConfig.default().gain_step_db

    if config.window_state is None:
        config.window_state = ""

    try:
        config.window_layout_version = int(config.window_layout_version)
    except (TypeError, ValueError):
        config.window_layout_version = 0
    if config.window_layout_version < 0:
        config.window_layout_version = 0

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
        payload.setdefault("demod_mode", DEFAULT_DEMOD_MODE)
        payload.setdefault(
            "channel_bandwidth_hz",
            default_bandwidth_hz(str(payload.get("demod_mode", DEFAULT_DEMOD_MODE))),
        )
        payload.setdefault("audio_volume", 0.5)
        payload.setdefault("freq_step_hz", 100_000.0)
        payload.setdefault("gain_step_db", 1.0)
    if from_version < 4:
        payload.setdefault("window_state", "")
    if from_version < 5:
        # Eski yüzer dock yerleşimini geri yükleme.
        payload["window_layout_version"] = 0
    payload["config_version"] = CONFIG_VERSION
    return payload
