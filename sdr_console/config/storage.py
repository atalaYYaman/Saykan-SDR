"""JSON persistence for ``AppConfig``."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

from sdr_console.config.app_config import AppConfig

DEFAULT_CONFIG_DIR = Path.home() / ".sdr-console"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.json"

logger = logging.getLogger(__name__)


def default_config_path() -> Path:
    return DEFAULT_CONFIG_PATH


def load_config(path: Path | None = None) -> AppConfig:
    """Load config from JSON or return defaults on missing/corrupt files."""
    config_path = path or default_config_path()
    if not config_path.exists():
        return AppConfig.default()

    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load config from %s (%s); using defaults", config_path, exc)
        return AppConfig.default()

    if not isinstance(raw, dict):
        logger.warning("Config file must contain a JSON object: %s; using defaults", config_path)
        return AppConfig.default()

    return AppConfig.from_dict(raw)


def save_config(config: AppConfig, path: Path | None = None) -> Path:
    """Persist config to JSON atomically, creating parent directories as needed."""
    config_path = path or default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(config.to_dict(), indent=2, sort_keys=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{config_path.name}.",
        suffix=".tmp",
        dir=str(config_path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, config_path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise

    return config_path
