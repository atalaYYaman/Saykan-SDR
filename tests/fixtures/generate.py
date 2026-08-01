"""Generate deterministic IQ fixture files under tests/fixtures/."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from sdr_console.hal.mock_device import DEFAULT_CENTER_FREQ_HZ, MockSDRDevice, MockTone

FIXTURES_DIR = Path(__file__).parent


def _save(name: str, iq: np.ndarray) -> Path:
    path = FIXTURES_DIR / name
    np.save(path, iq.astype(np.complex64))
    return path


def generate_all() -> list[Path]:
    """Write single_tone, three_tones, and noise_only fixtures."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    sample_rate = 2_048_000.0
    n = 8192
    center = DEFAULT_CENTER_FREQ_HZ

    single = MockSDRDevice(
        sample_rate_hz=sample_rate,
        center_freq_hz=center,
        gain_db=50.0,
        tones=(MockTone(center + 50_000.0, 1.0),),
        noise_amplitude=0.0,
        realtime=False,
    )
    single.connect()
    single_iq = single.read_samples(n)
    single.disconnect()

    three = MockSDRDevice(
        sample_rate_hz=sample_rate,
        center_freq_hz=center,
        gain_db=50.0,
        tones=(
            MockTone(center - 120_000.0, 1.0),
            MockTone(center + 40_000.0, 1.0),
            MockTone(center + 180_000.0, 1.0),
        ),
        noise_amplitude=0.0,
        realtime=False,
    )
    three.connect()
    three_iq = three.read_samples(n)
    three.disconnect()

    noise = MockSDRDevice(
        sample_rate_hz=sample_rate,
        center_freq_hz=center,
        tones=(),
        noise_amplitude=0.05,
        realtime=False,
        rng=np.random.default_rng(0),
    )
    noise.connect()
    noise_iq = noise.read_samples(n)
    noise.disconnect()

    return [
        _save("single_tone.npy", single_iq),
        _save("three_tones.npy", three_iq),
        _save("noise_only.npy", noise_iq),
    ]


if __name__ == "__main__":
    paths = generate_all()
    for path in paths:
        print(path)
