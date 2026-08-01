"""Unit tests for PlutoSDRDevice using a fake pyadi-iio module."""

from __future__ import annotations

import sys
import types
from typing import Any

import numpy as np
import pytest

from sdr_console.hal.errors import DeviceUnavailableError
from sdr_console.hal.pluto_device import (
    PLUTO_CAPABILITIES,
    PlutoSDRDevice,
    parse_available_range,
)


class _FakeAttr:
    def __init__(self, value: str) -> None:
        self.value = value


class _FakeChannel:
    def __init__(
        self,
        name: str,
        attrs: dict[str, _FakeAttr],
        *,
        output: bool = False,
        channel_id: str | None = None,
    ) -> None:
        self.name = name
        self.id = channel_id or name
        self.output = output
        self.attrs = attrs


class _FakeDevice:
    def __init__(self, channels: list[_FakeChannel]) -> None:
        self.channels = channels


class _FakeContext:
    def __init__(self, devices: list[_FakeDevice]) -> None:
        self.devices = devices


class FakePluto:
    """Minimal stand-in for adi.Pluto used in unit tests."""

    def __init__(self, uri: str | None = None) -> None:
        self.uri = uri
        self.rx_enabled_channels = [0]
        self.rx_buffer_size = 1024
        self.sample_rate = 2_048_000
        self.rx_rf_bandwidth = 2_048_000
        self.rx_lo = 100_000_000
        self.gain_control_mode_chan0 = "manual"
        self.rx_hardwaregain_chan0 = 40.0
        self._rx_calls = 0
        self._ctx = _FakeContext(
            [
                _FakeDevice(
                    [
                        _FakeChannel(
                            "RX_LO",
                            {
                                "frequency_available": _FakeAttr(
                                    "[70000000 1 6000000000]"
                                )
                            },
                        ),
                        _FakeChannel(
                            "voltage0",
                            {
                                "sampling_frequency_available": _FakeAttr(
                                    "[520833 1 61440000]"
                                ),
                                "hardwaregain_available": _FakeAttr("[-3 1 71]"),
                            },
                        ),
                    ]
                )
            ]
        )

    def rx(self) -> np.ndarray:
        self._rx_calls += 1
        # Full-scale tone peak at +2048 (ADC full scale).
        return np.full(self.rx_buffer_size, 2048 + 0j, dtype=np.complex64)

    def rx_destroy_buffer(self) -> None:
        return None


def _install_fake_adi(monkeypatch: pytest.MonkeyPatch, pluto_cls: type = FakePluto) -> None:
    adi = types.ModuleType("adi")
    adi.Pluto = pluto_cls  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "adi", adi)


def test_parse_available_range() -> None:
    assert parse_available_range("[70000000 1 6000000000]") == (
        70_000_000.0,
        1.0,
        6_000_000_000.0,
    )
    assert parse_available_range("  [-3 1 71] ") == (-3.0, 1.0, 71.0)
    assert parse_available_range("not a range") is None


def test_pluto_unavailable_without_adi(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "adi", None)  # type: ignore[dict-item]

    # Force ImportError path by removing adi if present and blocking import.
    monkeypatch.delitem(sys.modules, "adi", raising=False)

    import builtins

    real_import = builtins.__import__

    def blocked(name: str, *args: Any, **kwargs: Any):
        if name == "adi" or name.startswith("adi."):
            raise ImportError("blocked")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)

    device = PlutoSDRDevice()
    with pytest.raises(DeviceUnavailableError, match="pyadi-iio"):
        device.connect()


def test_pluto_requires_connection() -> None:
    device = PlutoSDRDevice()
    with pytest.raises(RuntimeError, match="not connected"):
        device.read_samples(128)


def test_pluto_scales_and_serves_exact_length(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_adi(monkeypatch)
    device = PlutoSDRDevice(
        sample_rate_hz=2_048_000.0,
        center_freq_hz=100_000_000.0,
        gain_db=40.0,
        rx_buffer_size=4096,
    )
    device.connect()

    assert device.is_connected
    assert device.capabilities.min_freq_hz == 70_000_000.0
    assert device.capabilities.max_freq_hz == 6_000_000_000.0
    assert device.capabilities.min_sample_rate_hz == pytest.approx(520_833.0)
    assert device.capabilities.max_gain_db == 71.0

    samples = device.read_samples(1024)
    assert samples.shape == (1024,)
    assert samples.dtype == np.complex64
    # 2048 / 2048 => unit magnitude
    assert np.max(np.abs(samples)) == pytest.approx(1.0, abs=1e-5)

    # Residual should serve another block without requiring a new rx() yet
    # until residual is exhausted (4096 - 1024 = 3072 left).
    fake = device._sdr
    assert fake is not None
    calls_before = fake._rx_calls
    more = device.read_samples(2048)
    assert more.shape == (2048,)
    assert fake._rx_calls == calls_before

    device.disconnect()
    assert not device.is_connected


def test_pluto_setters_update_fake_hardware(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_adi(monkeypatch)
    device = PlutoSDRDevice(gain_db=30.0, gain_mode="manual")
    device.connect()
    device.set_center_freq(433_000_000.0)
    device.set_sample_rate(1_000_000.0)
    device.set_gain(50.0)
    device.set_gain_mode("slow_attack")

    sdr = device._sdr
    assert sdr.rx_lo == 433_000_000
    assert sdr.sample_rate == 1_000_000
    assert sdr.rx_rf_bandwidth == 1_000_000
    assert sdr.gain_control_mode_chan0 == "slow_attack"
    assert device.gain_mode == "slow_attack"

    device.disconnect()


def test_static_pluto_capabilities_are_continuous() -> None:
    assert PLUTO_CAPABILITIES.has_continuous_sample_rates
    PLUTO_CAPABILITIES.validate_sample_rate_hz(3_000_000.0)
