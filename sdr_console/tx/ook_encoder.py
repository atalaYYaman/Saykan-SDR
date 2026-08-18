"""OOK bit/darbe zamanlamasından TX IQ waveform üretimi."""

from __future__ import annotations

import numpy as np

from sdr_console.tx.capture_decoder import OokCapture, PulseEvent


def encode_ook(
    bits: list[int],
    bit_duration_s: float,
    sample_rate: float,
    amplitude: float,
) -> np.ndarray:
    """Bit dizisinden ON genişliği kodlamalı OOK IQ üret.

    Kısa ON = 0, uzun ON = 1; her bit arasında ``bit_duration_s`` boşluk.
    """
    if bit_duration_s <= 0:
        raise ValueError("bit_duration_s must be positive")
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    if amplitude <= 0:
        raise ValueError("amplitude must be positive")
    if not bits:
        raise ValueError("bits must not be empty")

    short_s = float(bit_duration_s)
    long_s = short_s * 2.0
    gap_s = short_s
    segments: list[np.ndarray] = []

    for bit in bits:
        if bit not in (0, 1):
            raise ValueError(f"invalid bit value: {bit}")
        on_s = long_s if bit else short_s
        n_on = max(1, int(round(on_s * sample_rate)))
        n_gap = max(1, int(round(gap_s * sample_rate)))
        segments.append(np.full(n_on, amplitude, dtype=np.float32))
        segments.append(np.zeros(n_gap, dtype=np.float32))

    envelope = np.concatenate(segments)
    return envelope.astype(np.complex64)


def encode_from_pulses(
    pulses: list[PulseEvent],
    sample_rate: float,
    amplitude: float,
) -> np.ndarray:
    """Ham darbe zamanlamasını doğrudan OOK IQ waveform'a çevir."""
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    if amplitude <= 0:
        raise ValueError("amplitude must be positive")
    if not pulses:
        raise ValueError("pulses must not be empty")

    segments: list[np.ndarray] = []
    for pulse in pulses:
        n_samples = max(1, int(round(pulse.duration_s * sample_rate)))
        value = amplitude if pulse.level else 0.0
        segments.append(np.full(n_samples, value, dtype=np.float32))

    envelope = np.concatenate(segments)
    return envelope.astype(np.complex64)


def encode_capture(
    capture: OokCapture,
    amplitude: float = 0.85,
    bit_duration_s: float | None = None,
) -> np.ndarray:
    """Yakalamayı yeniden üretim için IQ'ya dönüştür.

    Önce ham ``pulses`` kullanılır; yalnızca bitler varsa ``encode_ook`` denenir.
    """
    if amplitude <= 0:
        raise ValueError("amplitude must be positive")

    if capture.pulses:
        return encode_from_pulses(list(capture.pulses), capture.sample_rate_hz, amplitude)

    if capture.bits is None:
        raise ValueError("capture has no pulses or bits to encode")

    duration = bit_duration_s if bit_duration_s is not None else 0.0003
    return encode_ook(list(capture.bits), duration, capture.sample_rate_hz, amplitude)
