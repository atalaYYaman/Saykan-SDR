"""Baraj karıştırma IQ — bant sınırlı gürültü, CW yok."""

from __future__ import annotations

import numpy as np

from sdr_console.ea.constants import BARRAGE_NOISE_RMS, DEFAULT_JAM_BANDWIDTH_HZ
from sdr_console.tx.waveform import clamp_bandwidth_hz, cyclic_length


def generate_barrage_noise(
    sample_rate_hz: float,
    bandwidth_hz: float = DEFAULT_JAM_BANDWIDTH_HZ,
    *,
    num_samples: int | None = None,
    noise_rms: float = BARRAGE_NOISE_RMS,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Birim ölçekte complex64: ``±bandwidth/2`` gürültü, DC'de CW yok.

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

    peak = float(np.max(np.abs(filtered)))
    if peak > 1.0:
        filtered /= peak
    return filtered.astype(np.complex64)
