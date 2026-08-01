"""Device labels and per-device constructor kwargs for the UI.

Re-exports HAL registry so UI does not own device identifiers.
"""

from __future__ import annotations

from typing import Any

from sdr_console.config.app_config import AppConfig
from sdr_console.config.defaults import AppDefaults
from sdr_console.hal.registry import (
    DEVICE_CHOICES,
    HACKRF_DEVICE_ID,
    MOCK_AM_DEVICE_ID,
    MOCK_DEVICE_ID,
    MOCK_DEVICE_LABEL,
    PLUTO_DEVICE_ID,
    RTLSDR_DEVICE_ID,
    device_availability,
)

__all__ = [
    "DEVICE_CHOICES",
    "MOCK_AM_DEVICE_ID",
    "MOCK_DEVICE_ID",
    "MOCK_DEVICE_LABEL",
    "device_availability",
    "device_create_kwargs",
]


def device_create_kwargs(
    device_id: str,
    config: AppConfig,
    runtime_defaults: AppDefaults,
) -> dict[str, Any]:
    """Build constructor kwargs appropriate for ``device_id``.

    Keeps mock-only parameters out of real hardware constructors so the
    registry factory does not need TypeError fallbacks.
    """
    common: dict[str, Any] = {
        "sample_rate_hz": config.sample_rate_hz,
        "center_freq_hz": config.center_freq_hz,
        "gain_db": config.gain_db,
    }

    if device_id in (MOCK_DEVICE_ID, MOCK_AM_DEVICE_ID):
        return {
            **common,
            "noise_amplitude": runtime_defaults.mock_noise_amplitude,
            "realtime": True,
        }

    if device_id == PLUTO_DEVICE_ID:
        return {
            **common,
            "uri": config.device_uri,
            "rx_buffer_size": config.rx_buffer_size,
            "gain_mode": config.gain_mode,
        }

    if device_id == RTLSDR_DEVICE_ID:
        return common

    if device_id == HACKRF_DEVICE_ID:
        return common

    return common
