"""Tests for FileIQDevice playback."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from sdr_console.hal.file_device import FileIQDevice
from sdr_console.hal.mock_device import DEFAULT_CENTER_FREQ_HZ


def _ensure_fixtures(fixtures_dir: Path) -> None:
    if not (fixtures_dir / "single_tone.npy").exists():
        from tests.fixtures.generate import generate_all

        generate_all()


def test_file_device_loops_fixture(fixtures_dir: Path) -> None:
    _ensure_fixtures(fixtures_dir)
    path = fixtures_dir / "single_tone.npy"
    device = FileIQDevice(
        path,
        sample_rate_hz=2_048_000.0,
        center_freq_hz=DEFAULT_CENTER_FREQ_HZ,
        gain_db=50.0,
    )
    device.connect()
    first = device.read_samples(1024)
    remaining = int(np.load(path).size) - 1024 + 64
    if remaining > 0:
        device.read_samples(remaining)
    wrapped = device.read_samples(64)
    device.disconnect()

    assert first.dtype == np.complex64
    assert first.shape == (1024,)
    assert wrapped.shape == (64,)
    assert float(np.max(np.abs(first))) > 0.1


def test_file_device_requires_connection(fixtures_dir: Path) -> None:
    _ensure_fixtures(fixtures_dir)
    device = FileIQDevice(fixtures_dir / "single_tone.npy")
    with pytest.raises(RuntimeError):
        device.read_samples(32)
