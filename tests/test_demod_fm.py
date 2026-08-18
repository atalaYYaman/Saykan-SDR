"""FM deviation normalisation and soft-limit tests (ADIM A2)."""

from __future__ import annotations

import numpy as np
import pytest

from sdr_console.demod.fm import NFMDemodulator, WFMDemodulator
from sdr_console.dsp.audio import soft_limit_audio
from sdr_console.dsp.channelizer import ChannelizedBlock


def make_fm_baseband(
    sample_rate_hz: float,
    num_samples: int,
    audio_freq_hz: float,
    peak_deviation_hz: float,
) -> np.ndarray:
    """Unit-magnitude FM tone: instantaneous deviation = peak · sin(2π f_a t)."""
    t = np.arange(num_samples, dtype=np.float64) / sample_rate_hz
    # φ'(t) = 2π · Δf(t)  ⇒  φ(t) = -(Δf_peak / f_a) · cos(2π f_a t)
    phase = -(peak_deviation_hz / audio_freq_hz) * np.cos(2.0 * np.pi * audio_freq_hz * t)
    return np.exp(1j * phase).astype(np.complex64)


def dominant_frequency_hz(audio: np.ndarray, audio_rate_hz: float) -> float:
    spectrum = np.abs(np.fft.rfft(audio * np.hanning(audio.size)))
    freqs = np.fft.rfftfreq(audio.size, d=1.0 / audio_rate_hz)
    spectrum[freqs < 20.0] = 0.0
    return float(freqs[int(np.argmax(spectrum))])


def test_soft_limit_is_identity_well_below_the_knee() -> None:
    samples = np.array([-0.5, -0.2, 0.0, 0.3, 0.8], dtype=np.float64)
    limited = soft_limit_audio(samples, limit=1.0, knee=0.1)
    np.testing.assert_allclose(limited, samples.astype(np.float32))


def test_soft_limit_approaches_limit_without_hard_rail() -> None:
    samples = np.array([-1.5, -1.1, 1.05, 2.0], dtype=np.float64)
    limited = soft_limit_audio(samples, limit=1.0, knee=0.1)
    hard = np.clip(samples, -1.0, 1.0).astype(np.float32)

    assert limited.dtype == np.float32
    assert np.all(np.abs(limited) <= 1.0 + 1e-6)
    # Soft path stays below the hard-clipped magnitude for mild overshoot.
    assert float(np.abs(limited[2])) < float(np.abs(hard[2]))
    assert float(np.abs(limited[0])) <= 1.0


def test_soft_limit_rejects_invalid_arguments() -> None:
    with pytest.raises(ValueError):
        soft_limit_audio(np.zeros(2), limit=0.0)
    with pytest.raises(ValueError):
        soft_limit_audio(np.zeros(2), limit=1.0, knee=1.0)


@pytest.mark.parametrize(
    ("demod_cls", "if_rate_hz", "peak_deviation_hz"),
    [
        (NFMDemodulator, 48_000.0, 5_000.0),
        (WFMDemodulator, 240_000.0, 75_000.0),
    ],
)
def test_fm_full_deviation_lands_near_unity_without_clipping(
    demod_cls,
    if_rate_hz: float,
    peak_deviation_hz: float,
) -> None:
    audio_freq_hz = 1_000.0
    demodulator = demod_cls(
        input_rate_hz=if_rate_hz,
        peak_deviation_hz=peak_deviation_hz,
        audio_decimation=1,
        deemphasis=False,
        agc_enabled=False,
    )
    assert demodulator.peak_deviation_hz == peak_deviation_hz

    iq = make_fm_baseband(
        if_rate_hz,
        num_samples=int(if_rate_hz * 0.25),
        audio_freq_hz=audio_freq_hz,
        peak_deviation_hz=peak_deviation_hz,
    )
    audio = demodulator.process(ChannelizedBlock(iq, if_rate_hz))
    settled = audio[audio.size // 4 :]

    peak = float(np.percentile(np.abs(settled), 99))
    rms = float(np.sqrt(np.mean(np.square(settled, dtype=np.float64))))
    crest = peak / max(rms, 1e-12)

    # Full deviation → ~±1; allow headroom for DC blocker / filter startup.
    assert 0.75 <= peak <= 1.05
    # Sine crest ≈ √2; a hard-clipped square wave collapses toward ≈1.
    assert crest > 1.25
    assert dominant_frequency_hz(settled, demodulator.audio_rate_hz) == pytest.approx(
        audio_freq_hz, rel=0.05
    )


@pytest.mark.parametrize(
    ("demod_cls", "if_rate_hz", "nominal_deviation_hz"),
    [
        (NFMDemodulator, 48_000.0, 5_000.0),
        (WFMDemodulator, 240_000.0, 75_000.0),
    ],
)
def test_fm_half_deviation_scales_amplitude_linearly(
    demod_cls,
    if_rate_hz: float,
    nominal_deviation_hz: float,
) -> None:
    audio_freq_hz = 800.0
    demodulator = demod_cls(
        input_rate_hz=if_rate_hz,
        peak_deviation_hz=nominal_deviation_hz,
        audio_decimation=1,
        deemphasis=False,
        agc_enabled=False,
    )
    iq = make_fm_baseband(
        if_rate_hz,
        num_samples=int(if_rate_hz * 0.25),
        audio_freq_hz=audio_freq_hz,
        peak_deviation_hz=0.5 * nominal_deviation_hz,
    )
    audio = demodulator.process(ChannelizedBlock(iq, if_rate_hz))
    settled = audio[audio.size // 4 :]
    peak = float(np.percentile(np.abs(settled), 99))

    assert 0.35 <= peak <= 0.65


def test_nfm_and_wfm_default_peak_deviations() -> None:
    assert NFMDemodulator.PEAK_DEVIATION_HZ == 5_000.0
    assert WFMDemodulator.PEAK_DEVIATION_HZ == 75_000.0
    assert NFMDemodulator(48_000.0).peak_deviation_hz == 5_000.0
    assert WFMDemodulator(240_000.0).peak_deviation_hz == 75_000.0


def test_overdeviation_is_soft_limited_not_square_wave() -> None:
    """2× deviation must compress gently — not become a hard ±1 square."""
    if_rate_hz = 48_000.0
    nominal = 5_000.0
    demodulator = NFMDemodulator(
        input_rate_hz=if_rate_hz,
        peak_deviation_hz=nominal,
        audio_decimation=1,
        deemphasis=False,
        agc_enabled=False,
    )
    iq = make_fm_baseband(
        if_rate_hz,
        num_samples=int(if_rate_hz * 0.25),
        audio_freq_hz=1_000.0,
        peak_deviation_hz=2.0 * nominal,
    )
    audio = demodulator.process(ChannelizedBlock(iq, if_rate_hz))
    settled = audio[audio.size // 4 :]

    peak = float(np.percentile(np.abs(settled), 99))
    rms = float(np.sqrt(np.mean(np.square(settled, dtype=np.float64))))
    crest = peak / max(rms, 1e-12)

    # Equivalent hard-clipped 2× sine (old clip_audio behaviour).
    t = np.arange(settled.size, dtype=np.float64) / if_rate_hz
    hard = np.clip(2.0 * np.sin(2.0 * np.pi * 1_000.0 * t), -1.0, 1.0)
    hard_peak = float(np.percentile(np.abs(hard), 99))
    hard_rms = float(np.sqrt(np.mean(np.square(hard, dtype=np.float64))))
    hard_crest = hard_peak / max(hard_rms, 1e-12)

    assert peak <= 1.0 + 1e-6
    assert crest > hard_crest
    assert float(np.mean(np.abs(settled) >= 0.999)) < float(
        np.mean(np.abs(hard) >= 0.999)
    )
