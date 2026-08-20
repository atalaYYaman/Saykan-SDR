"""Test-sinyali IQ üretimi — bant sınırlı gürültü + zayıf CW."""

from __future__ import annotations

import numpy as np

from sdr_console.tx.constants import (
    DEFAULT_TX_BANDWIDTH_HZ,
    PLUTO_MIN_TX_RF_BANDWIDTH_HZ,
    TX_NOISE_RMS,
    TX_TONE_AMPLITUDE,
)

_MIN_CYCLIC_SAMPLES = 4_096
_MAX_CYCLIC_SAMPLES = 65_536


def clamp_bandwidth_hz(bandwidth_hz: float, sample_rate_hz: float) -> float:
    """İşgal edilen bant genişliğini ``(0, sample_rate]`` aralığına sıkıştır."""
    rate = float(sample_rate_hz)
    if rate <= 0:
        raise ValueError("sample_rate_hz must be positive")
    bandwidth = float(bandwidth_hz)
    if bandwidth <= 0:
        raise ValueError("bandwidth_hz must be positive")
    return min(bandwidth, rate)


def cyclic_length(
    sample_rate_hz: float,
    bandwidth_hz: float,
    *,
    minimum: int = _MIN_CYCLIC_SAMPLES,
    maximum: int = _MAX_CYCLIC_SAMPLES,
) -> int:
    """Cyclic TX tamponu: bant çözünürlüğü yeterli, USB'yi şişirmeyen 2'nin kuvveti."""
    rate = float(sample_rate_hz)
    bandwidth = clamp_bandwidth_hz(bandwidth_hz, rate)
    # En az ~16 FFT bin bant içinde kalsın.
    needed = int(rate / max(bandwidth / 16.0, 1.0))
    target = max(int(minimum), needed)
    length = 1
    while length < target:
        length *= 2
    return min(length, int(maximum))


def analog_tx_rf_bandwidth_hz(bandwidth_hz: float, sample_rate_hz: float) -> float:
    """Pluto analog TX filtresi: işgal edilen bant ile AD9363 alt sınırının büyüğü."""
    occupied = clamp_bandwidth_hz(bandwidth_hz, sample_rate_hz)
    return min(float(sample_rate_hz), max(occupied, PLUTO_MIN_TX_RF_BANDWIDTH_HZ))


def generate_noise_plus_tone(
    sample_rate_hz: float,
    bandwidth_hz: float = DEFAULT_TX_BANDWIDTH_HZ,
    *,
    num_samples: int | None = None,
    tone_amplitude: float = TX_TONE_AMPLITUDE,
    noise_rms: float = TX_NOISE_RMS,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Birim ölçekte complex64: DC'de CW + ``±bandwidth/2`` gürültü.

    Cyclic yayın için kısa bir çerçeve üretir; burst süresi TX cihazının
    ``max_duration_s`` zamanlayıcısıyla sınırlanır.
    """
    rate = float(sample_rate_hz)
    occupied = clamp_bandwidth_hz(bandwidth_hz, rate)
    length = int(num_samples) if num_samples is not None else cyclic_length(rate, occupied)
    if length <= 0:
        raise ValueError("num_samples must be positive")

    generator = rng if rng is not None else np.random.default_rng()
    noise = (
        generator.standard_normal(length) + 1j * generator.standard_normal(length)
    ).astype(np.complex128)
    spectrum = np.fft.fft(noise)
    freqs = np.fft.fftfreq(length, d=1.0 / rate)
    spectrum[np.abs(freqs) > occupied / 2.0] = 0.0
    filtered = np.fft.ifft(spectrum)
    rms = float(np.sqrt(np.mean(np.abs(filtered) ** 2)))
    if rms > 0.0 and noise_rms > 0.0:
        filtered *= noise_rms / rms
    else:
        filtered *= 0.0

    tone = np.full(length, float(tone_amplitude), dtype=np.complex128)
    mixed = filtered + tone
    peak = float(np.max(np.abs(mixed)))
    if peak > 1.0:
        mixed /= peak
    return mixed.astype(np.complex64)
