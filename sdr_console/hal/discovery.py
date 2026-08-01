"""Device discovery helpers for real SDR hardware."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DiscoveredDevice:
    """A hardware instance found on USB or the network."""

    device_id: str
    uri: str
    label: str
    serial: str = ""


def scan_devices() -> tuple[DiscoveredDevice, ...]:
    """Scan for attached SDR devices and return discovered instances.

    Currently probes libiio contexts for ADALM-Pluto. Returns an empty
    tuple when libiio is not installed or no contexts are found.
    """
    found: list[DiscoveredDevice] = []
    found.extend(_scan_pluto())
    return tuple(found)


def _looks_like_pluto(uri: str, description: str) -> bool:
    text = f"{uri} {description}".lower()
    return any(
        token in text
        for token in ("pluto", "plutosdr", "ad9361", "ad9363", "ad9364", "adalm")
    )


def _extract_serial(description: str) -> str:
    if "(" not in description or ")" not in description:
        return ""
    inner = description.rsplit("(", 1)[-1].rstrip(")")
    if inner and " " not in inner and len(inner) >= 4:
        return inner
    return ""


def _scan_pluto() -> list[DiscoveredDevice]:
    try:
        import iio  # type: ignore[import-untyped]
    except ImportError:
        logger.debug("libiio (iio) not available; skipping Pluto scan")
        return []

    try:
        contexts = iio.scan_contexts()
    except Exception:
        logger.exception("iio.scan_contexts failed")
        return []

    devices: list[DiscoveredDevice] = []
    for uri, description in contexts.items():
        uri_str = str(uri)
        desc_str = str(description)
        if not _looks_like_pluto(uri_str, desc_str):
            continue

        serial = _extract_serial(desc_str)
        label = f"ADALM-Pluto ({uri_str})"
        if serial:
            label = f"ADALM-Pluto {serial} ({uri_str})"

        devices.append(
            DiscoveredDevice(
                device_id="pluto",
                uri=uri_str,
                label=label,
                serial=serial,
            )
        )

    return devices
