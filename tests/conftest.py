"""Shared pytest fixtures for SDR Console tests."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from sdr_console.dsp.spectrum import compute_spectrum_frame
from sdr_console.hal.mock_device import (
    DEFAULT_CENTER_FREQ_HZ,
    MockSDRDevice,
    MockTone,
)

# Prefer offscreen Qt for headless CI / agent environments.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def make_tone_iq(fft_size: int, sample_rate: float, tone_hz: float) -> np.ndarray:
    """Synthesize a unit-amplitude complex tone at baseband offset ``tone_hz``."""
    sample_indices = np.arange(fft_size, dtype=np.float64)
    phase = 2.0 * np.pi * tone_hz * sample_indices / sample_rate
    return np.exp(1j * phase).astype(np.complex64)


def expected_peak_bin(fft_size: int, sample_rate: float, tone_hz: float) -> int:
    bin_hz = sample_rate / fft_size
    return fft_size // 2 + int(round(tone_hz / bin_hz))


@pytest.fixture
def tone_iq() -> np.ndarray:
    return make_tone_iq(1024, 2_048_000.0, 50_000.0)


@pytest.fixture
def mock_device() -> MockSDRDevice:
    return MockSDRDevice(
        tones=(MockTone(DEFAULT_CENTER_FREQ_HZ + 50_000.0, 1.0),),
        noise_amplitude=0.0,
        realtime=False,
    )


@pytest.fixture
def spectrum_frame(tone_iq: np.ndarray):
    return compute_spectrum_frame(
        tone_iq,
        fft_size=1024,
        center_freq=DEFAULT_CENTER_FREQ_HZ,
        sample_rate=2_048_000.0,
        timestamp=0.0,
    )


@pytest.fixture
def tmp_config_path(tmp_path: Path) -> Path:
    return tmp_path / "config.json"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR
