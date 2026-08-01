"""Unit tests for config persistence."""

import json
from pathlib import Path

from sdr_console.config.app_config import CONFIG_VERSION, DEFAULT_DEVICE_ID, AppConfig
from sdr_console.config.storage import load_config, save_config


def test_app_config_default_values() -> None:
    config = AppConfig.default()

    assert config.device_id == DEFAULT_DEVICE_ID
    assert config.fft_size == 1024
    assert config.center_freq_hz == 100_000_000.0


def test_app_config_from_dict_ignores_unknown_keys() -> None:
    config = AppConfig.from_dict(
        {
            "gain_db": 33.0,
            "unexpected_field": "ignored",
        }
    )

    assert config.gain_db == 33.0
    assert config.fft_size == 1024


def test_app_config_sanitizes_invalid_fields() -> None:
    config = AppConfig.from_dict(
        {
            "device_id": "not-a-real-device",
            "fft_size": "big",
            "display_vmin_db": 10.0,
            "display_vmax_db": -5.0,
        }
    )

    assert config.device_id == DEFAULT_DEVICE_ID
    assert config.fft_size == 1024
    assert config.display_vmin_db < config.display_vmax_db


def test_app_config_v2_fields_and_migration() -> None:
    config = AppConfig.from_dict(
        {
            "config_version": 1,
            "device_id": "mock",
            "center_freq_hz": 120e6,
        }
    )
    assert config.config_version == CONFIG_VERSION
    assert config.device_uri == ""
    assert config.gain_mode == "manual"
    assert config.rx_buffer_size == 16_384

    config2 = AppConfig.from_dict(
        {
            "config_version": 2,
            "device_uri": "ip:192.168.2.1",
            "gain_mode": "slow_attack",
            "rx_buffer_size": 8192,
            "device_id": "pluto",
        }
    )
    assert config2.device_id == "pluto"
    assert config2.device_uri == "ip:192.168.2.1"
    assert config2.gain_mode == "slow_attack"
    assert config2.rx_buffer_size == 8192


def test_app_config_v3_channel_fields_and_migration() -> None:
    migrated = AppConfig.from_dict(
        {
            "config_version": 2,
            "device_id": "mock",
            "center_freq_hz": 120e6,
        }
    )
    assert migrated.config_version == CONFIG_VERSION
    assert migrated.listen_freq_hz == 120e6
    assert migrated.channel_bandwidth_hz == 200_000.0
    assert migrated.demod_mode == "AM"

    explicit = AppConfig.from_dict(
        {
            "config_version": CONFIG_VERSION,
            "listen_freq_hz": 100_150_000.0,
            "channel_bandwidth_hz": 125_000.0,
            "demod_mode": "N-FM",
            "audio_volume": 0.8,
            "freq_step_hz": 25_000.0,
            "gain_step_db": 0.5,
        }
    )
    assert explicit.listen_freq_hz == 100_150_000.0
    assert explicit.channel_bandwidth_hz == 125_000.0
    assert explicit.demod_mode == "N-FM"
    assert explicit.audio_volume == 0.8
    assert explicit.freq_step_hz == 25_000.0
    assert explicit.gain_step_db == 0.5


def test_app_config_sanitizes_channel_and_audio_fields() -> None:
    config = AppConfig.from_dict(
        {
            "channel_bandwidth_hz": 0.0,
            "audio_volume": 4.0,
            "freq_step_hz": -1.0,
            "gain_step_db": 0.0,
            "demod_mode": "",
        }
    )

    assert config.channel_bandwidth_hz == 200_000.0
    assert config.audio_volume == 1.0
    assert config.freq_step_hz > 0.0
    assert config.gain_step_db > 0.0
    assert config.demod_mode == "AM"


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    original = AppConfig.default()
    original.device_id = DEFAULT_DEVICE_ID
    original.center_freq_hz = 433_920_000.0
    original.gain_db = 28.5
    original.fft_size = 2048

    save_config(original, config_path)
    loaded = load_config(config_path)

    assert loaded.device_id == DEFAULT_DEVICE_ID
    assert loaded.center_freq_hz == 433_920_000.0
    assert loaded.gain_db == 28.5
    assert loaded.fft_size == 2048
    assert loaded.config_version == CONFIG_VERSION


def test_load_missing_file_returns_defaults(tmp_path: Path) -> None:
    loaded = load_config(tmp_path / "missing.json")
    assert loaded == AppConfig.default()


def test_load_rejects_non_object_json(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

    loaded = load_config(config_path)
    assert loaded == AppConfig.default()


def test_load_malformed_json_returns_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text("{ not valid json", encoding="utf-8")

    loaded = load_config(config_path)
    assert loaded == AppConfig.default()
