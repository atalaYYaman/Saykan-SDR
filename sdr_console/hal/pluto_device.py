"""ADALM-Pluto driver via pyadi-iio (lazy import)."""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import replace
from typing import Any

import numpy as np

from sdr_console.hal.capabilities import DeviceCapabilities
from sdr_console.hal.errors import DeviceConnectionError, DeviceUnavailableError
from sdr_console.hal.interface import SDRDeviceInterface

logger = logging.getLogger(__name__)

# Conservative static limits used before connect() probes the hardware.
# Covers both stock AD9363 and AD9364-hacked Pluto boards.
PLUTO_CAPABILITIES = DeviceCapabilities(
    min_freq_hz=70_000_000.0,
    max_freq_hz=6_000_000_000.0,
    supported_sample_rates_hz=(
        521_000.0,
        1_000_000.0,
        2_048_000.0,
        2_500_000.0,
        5_000_000.0,
        10_000_000.0,
        20_000_000.0,
    ),
    min_gain_db=-3.0,
    max_gain_db=71.0,
    min_sample_rate_hz=521_000.0,
    max_sample_rate_hz=61_440_000.0,
    gain_modes=("manual", "slow_attack", "fast_attack", "hybrid"),
)

_FULL_SCALE_DEFAULT = 2048.0  # 12-bit ADC peak in pyadi-iio complex samples
_AVAILABLE_RE = re.compile(
    r"\[\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s+"
    r"([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s+"
    r"([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*\]"
)


def parse_available_range(raw: str) -> tuple[float, float, float] | None:
    """Parse a libiio ``*_available`` string of the form ``[min step max]``.

    Returns ``(min, step, max)`` or ``None`` when the format is unrecognized.
    """
    match = _AVAILABLE_RE.search(raw.strip())
    if match is None:
        return None
    return float(match.group(1)), float(match.group(2)), float(match.group(3))


class PlutoSDRDevice(SDRDeviceInterface):
    """ADALM-Pluto receiver implementing :class:`SDRDeviceInterface`.

    ``adi`` (pyadi-iio) is imported lazily inside :meth:`connect` so the rest
    of the application starts without the optional Pluto extra installed.
    """

    def __init__(
        self,
        sample_rate_hz: float = 2_048_000.0,
        center_freq_hz: float = 100_000_000.0,
        gain_db: float = 40.0,
        uri: str = "",
        rx_buffer_size: int = 16_384,
        full_scale: float = _FULL_SCALE_DEFAULT,
        gain_mode: str = "manual",
        capabilities: DeviceCapabilities = PLUTO_CAPABILITIES,
    ) -> None:
        if rx_buffer_size <= 0:
            raise ValueError("rx_buffer_size must be positive")
        if full_scale <= 0:
            raise ValueError("full_scale must be positive")

        self._capabilities = capabilities
        self._center_freq_hz = float(center_freq_hz)
        self._sample_rate_hz = float(sample_rate_hz)
        self._gain_db = float(gain_db)
        self._gain_mode = gain_mode
        self._uri = uri.strip()
        self._rx_buffer_size = int(rx_buffer_size)
        self._full_scale = float(full_scale)

        self._capabilities.validate_freq_hz(self._center_freq_hz)
        self._capabilities.validate_sample_rate_hz(self._sample_rate_hz)
        self._capabilities.validate_gain_db(self._gain_db)
        self._capabilities.validate_gain_mode(self._gain_mode)

        self._sdr: Any | None = None
        self._connected = False
        self._lock = threading.RLock()
        self._residual: np.ndarray = np.empty(0, dtype=np.complex64)

    # ------------------------------------------------------------------ TX attachment (shared IIO)

    @property
    def iio_backend(self) -> Any | None:
        """Live pyadi-iio handle for TX on the same USB context. None if disconnected."""
        return self._sdr

    @property
    def iio_lock(self) -> threading.RLock:
        """Lock covering all libiio access; TX must share this with RX reads."""
        return self._lock

    # ------------------------------------------------------------------ properties

    @property
    def capabilities(self) -> DeviceCapabilities:
        return self._capabilities

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def center_freq_hz(self) -> float:
        return self._center_freq_hz

    @property
    def sample_rate_hz(self) -> float:
        return self._sample_rate_hz

    @property
    def gain_db(self) -> float:
        return self._gain_db

    @property
    def gain_mode(self) -> str:
        return self._gain_mode

    @property
    def uri(self) -> str:
        return self._uri

    @property
    def rx_buffer_size(self) -> int:
        return self._rx_buffer_size

    # ------------------------------------------------------------------ lifecycle

    def connect(self) -> None:
        with self._lock:
            if self._connected:
                return

            try:
                import adi  # type: ignore[import-untyped]
            except ImportError as exc:
                raise DeviceUnavailableError(
                    "pyadi-iio is not installed. Install with: pip install -e \".[pluto]\""
                ) from exc

            try:
                if self._uri:
                    sdr = adi.Pluto(uri=self._uri)
                else:
                    sdr = adi.Pluto()
            except Exception as exc:
                raise DeviceConnectionError(
                    "Failed to open ADALM-Pluto"
                    + (f" at {self._uri!r}" if self._uri else "")
                    + f": {exc}"
                ) from exc

            self._sdr = sdr
            try:
                self._apply_all_settings()
                self._capabilities = self._probe_capabilities(sdr)
                # Re-validate after probe (ranges may have narrowed).
                self._capabilities.validate_freq_hz(self._center_freq_hz)
                self._capabilities.validate_sample_rate_hz(self._sample_rate_hz)
                self._capabilities.validate_gain_db(self._gain_db)
                self._capabilities.validate_gain_mode(self._gain_mode)
                self._apply_all_settings()
            except Exception:
                self._destroy_sdr()
                raise

            self._residual = np.empty(0, dtype=np.complex64)
            self._connected = True
            logger.info(
                "Pluto connected uri=%r rate=%g freq=%g gain=%g mode=%s",
                self._uri or "auto",
                self._sample_rate_hz,
                self._center_freq_hz,
                self._gain_db,
                self._gain_mode,
            )

    def disconnect(self) -> None:
        with self._lock:
            self._connected = False
            self._residual = np.empty(0, dtype=np.complex64)
            self._destroy_sdr()

    def _destroy_sdr(self) -> None:
        sdr = self._sdr
        self._sdr = None
        if sdr is None:
            return
        try:
            # Prefer explicit buffer destroy when available.
            destroy = getattr(sdr, "rx_destroy_buffer", None)
            if callable(destroy):
                destroy()
        except Exception:
            logger.debug("rx_destroy_buffer failed during disconnect", exc_info=True)
        try:
            del sdr
        except Exception:
            pass

    # ------------------------------------------------------------------ setters

    def set_center_freq(self, freq_hz: float) -> None:
        self._capabilities.validate_freq_hz(freq_hz)
        with self._lock:
            self._center_freq_hz = float(freq_hz)
            if self._sdr is not None:
                self._sdr.rx_lo = int(self._center_freq_hz)

    def set_sample_rate(self, rate_hz: float) -> None:
        self._capabilities.validate_sample_rate_hz(rate_hz)
        with self._lock:
            self._sample_rate_hz = float(rate_hz)
            if self._sdr is not None:
                self._sdr.sample_rate = int(self._sample_rate_hz)
                self._sdr.rx_rf_bandwidth = int(self._sample_rate_hz)
                self._residual = np.empty(0, dtype=np.complex64)

    def set_gain(self, gain_db: float) -> None:
        self._capabilities.validate_gain_db(gain_db)
        with self._lock:
            self._gain_db = float(gain_db)
            if self._sdr is not None and self._gain_mode == "manual":
                self._sdr.rx_hardwaregain_chan0 = self._gain_db

    def set_gain_mode(self, mode: str) -> None:
        self._capabilities.validate_gain_mode(mode)
        with self._lock:
            self._gain_mode = mode
            if self._sdr is not None:
                self._sdr.gain_control_mode_chan0 = mode
                if mode == "manual":
                    self._sdr.rx_hardwaregain_chan0 = self._gain_db

    # ------------------------------------------------------------------ IQ read

    def read_samples(self, num_samples: int) -> np.ndarray:
        if not self._connected or self._sdr is None:
            raise RuntimeError("PlutoSDRDevice is not connected")
        if num_samples <= 0:
            raise ValueError("num_samples must be positive")

        with self._lock:
            if not self._connected or self._sdr is None:
                raise RuntimeError("PlutoSDRDevice is not connected")

            while self._residual.size < num_samples:
                try:
                    chunk = self._sdr.rx()
                except Exception as exc:
                    self._connected = False
                    raise RuntimeError(f"Pluto read failed: {exc}") from exc

                scaled = self._scale_iq(chunk)
                if self._residual.size == 0:
                    self._residual = scaled
                else:
                    self._residual = np.concatenate((self._residual, scaled))

            out = self._residual[:num_samples]
            self._residual = self._residual[num_samples:]
            return out

    def _scale_iq(self, raw: Any) -> np.ndarray:
        """Convert pyadi-iio IQ block to unit-scale complex64."""
        arr = np.asarray(raw)
        if arr.ndim != 1:
            arr = arr.reshape(-1)
        return (arr.astype(np.complex128) / self._full_scale).astype(np.complex64)

    # ------------------------------------------------------------------ probe / apply

    def _apply_all_settings(self) -> None:
        assert self._sdr is not None
        sdr = self._sdr
        sdr.rx_enabled_channels = [0]
        sdr.tx_enabled_channels = [0]
        sdr.rx_buffer_size = self._rx_buffer_size
        sdr.sample_rate = int(self._sample_rate_hz)
        sdr.rx_rf_bandwidth = int(self._sample_rate_hz)
        sdr.tx_rf_bandwidth = int(self._sample_rate_hz)
        sdr.rx_lo = int(self._center_freq_hz)
        sdr.tx_lo = int(self._center_freq_hz)
        sdr.tx_hardwaregain_chan0 = -89.0
        sdr.gain_control_mode_chan0 = self._gain_mode
        if self._gain_mode == "manual":
            sdr.rx_hardwaregain_chan0 = self._gain_db
        loopback = getattr(sdr, "loopback", None)
        if loopback is not None:
            try:
                sdr.loopback = 0
            except Exception:
                logger.debug("Pluto loopback reset failed", exc_info=True)

    def _probe_capabilities(self, sdr: Any) -> DeviceCapabilities:
        """Read real hardware limits from libiio attributes when available."""
        caps = self._capabilities
        freq_range = self._read_attr_range(sdr, "RX_LO", "frequency_available")
        rate_range = self._read_attr_range(
            sdr, "voltage0", "sampling_frequency_available"
        )
        # hardwaregain lives on the RX voltage channel.
        gain_range = self._read_attr_range(sdr, "voltage0", "hardwaregain_available")
        if gain_range is None:
            gain_range = self._read_attr_range(
                sdr, "voltage0", "hardwaregain_available", output=False
            )

        updates: dict[str, Any] = {}
        if freq_range is not None:
            updates["min_freq_hz"] = float(freq_range[0])
            updates["max_freq_hz"] = float(freq_range[2])
        if rate_range is not None:
            updates["min_sample_rate_hz"] = float(rate_range[0])
            updates["max_sample_rate_hz"] = float(rate_range[2])
            presets = tuple(
                r
                for r in caps.supported_sample_rates_hz
                if rate_range[0] <= r <= rate_range[2]
            )
            if presets:
                updates["supported_sample_rates_hz"] = presets
        if gain_range is not None:
            updates["min_gain_db"] = float(gain_range[0])
            updates["max_gain_db"] = float(gain_range[2])

        if not updates:
            return caps
        return replace(caps, **updates)

    @staticmethod
    def _read_attr_range(
        sdr: Any,
        channel_name: str,
        attr_name: str,
        *,
        output: bool = False,
    ) -> tuple[float, float, float] | None:
        """Best-effort read of a libiio ``[min step max]`` channel attribute."""
        try:
            ctx = getattr(sdr, "_ctx", None) or getattr(sdr, "ctx", None)
            if ctx is None:
                return None
            for device in ctx.devices:
                for channel in device.channels:
                    if channel.name != channel_name and channel.id != channel_name:
                        continue
                    if bool(channel.output) != output:
                        continue
                    attrs = getattr(channel, "attrs", {})
                    if attr_name not in attrs:
                        continue
                    raw = attrs[attr_name].value
                    parsed = parse_available_range(str(raw))
                    if parsed is not None:
                        return parsed
        except Exception:
            logger.debug(
                "Failed reading %s/%s from Pluto", channel_name, attr_name, exc_info=True
            )
        return None
