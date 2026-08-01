"""Tests for FM, SSB and CW demodulators against mock transmitters."""

from __future__ import annotations

import numpy as np
import pytest

from sdr_console.demod.cw import DEFAULT_BFO_OFFSET_HZ, CWDemodulator
from sdr_console.demod.fm import NFMDemodulator, WFMDemodulator
from sdr_console.demod.ssb import LSBDemodulator, USBDemodulator
from sdr_console.dsp.channel import ChannelSpec
from sdr_console.dsp.channelizer import channelize, plan_channelizer
from sdr_console.hal.scenarios import cw_tone, fm_tone, lsb_tone, usb_tone

CENTER_HZ = 100_000_000.0
SAMPLE_RATE_HZ = 2_048_000.0
CARRIER_OFFSET_HZ = 50_000.0
AUDIO_FREQ_HZ = 1_000.0
BLOCK = 32_768


def dominant_frequency_hz(audio: np.ndarray, audio_rate_hz: float) -> float:
    spectrum = np.abs(np.fft.rfft(audio * np.hanning(audio.size)))
    freqs = np.fft.rfftfreq(audio.size, d=1.0 / audio_rate_hz)
    spectrum[freqs < 20.0] = 0.0
    return float(freqs[int(np.argmax(spectrum))])


def demodulate_stream(device, demodulator, channel, plan, num_blocks: int = 6) -> np.ndarray:
    chunks = []
    state = None
    for _ in range(num_blocks):
        iq = device.read_samples(BLOCK)
        block, state = channelize(
            iq,
            channel,
            device.center_freq_hz,
            device.sample_rate_hz,
            plan,
            state=state,
        )
        chunks.append(demodulator.process(block))
    return np.concatenate(chunks)


@pytest.mark.parametrize(
    ("factory", "demod_cls", "bandwidth_hz", "peak_deviation_hz"),
    [
        (fm_tone, NFMDemodulator, 12_500.0, 5_000.0),
        (fm_tone, WFMDemodulator, 200_000.0, 75_000.0),
    ],
)
def test_fm_demodulator_recovers_the_modulating_tone(
    factory,
    demod_cls,
    bandwidth_hz: float,
    peak_deviation_hz: float,
) -> None:
    device = factory(
        offset_hz=CARRIER_OFFSET_HZ,
        audio_freq_hz=AUDIO_FREQ_HZ,
        peak_deviation_hz=peak_deviation_hz,
        center_freq_hz=CENTER_HZ,
        sample_rate_hz=SAMPLE_RATE_HZ,
    )
    device.connect()

    channel = ChannelSpec(CENTER_HZ + CARRIER_OFFSET_HZ, bandwidth_hz)
    plan = plan_channelizer(channel.bandwidth_hz, SAMPLE_RATE_HZ, 48_000.0)
    demodulator = demod_cls(input_rate_hz=plan.output_rate_hz)

    audio = demodulate_stream(device, demodulator, channel, plan)
    settled = audio[audio.size // 4 :]
    peak_hz = dominant_frequency_hz(settled, demodulator.audio_rate_hz)

    assert demodulator.mode == demod_cls.MODE
    assert peak_hz == pytest.approx(AUDIO_FREQ_HZ, rel=0.08)
    assert np.all(np.abs(audio) <= 1.0)


@pytest.mark.parametrize(
    ("factory", "demod_cls"),
    [
        (usb_tone, USBDemodulator),
        (lsb_tone, LSBDemodulator),
    ],
)
def test_ssb_demodulator_recovers_the_modulating_tone(factory, demod_cls) -> None:
    device = factory(
        offset_hz=CARRIER_OFFSET_HZ,
        audio_freq_hz=AUDIO_FREQ_HZ,
        center_freq_hz=CENTER_HZ,
        sample_rate_hz=SAMPLE_RATE_HZ,
    )
    device.connect()

    channel = ChannelSpec(CENTER_HZ + CARRIER_OFFSET_HZ, 3_000.0)
    plan = plan_channelizer(channel.bandwidth_hz, SAMPLE_RATE_HZ, 48_000.0)
    demodulator = demod_cls(input_rate_hz=plan.output_rate_hz)

    audio = demodulate_stream(device, demodulator, channel, plan)
    settled = audio[audio.size // 4 :]
    peak_hz = dominant_frequency_hz(settled, demodulator.audio_rate_hz)

    assert peak_hz == pytest.approx(AUDIO_FREQ_HZ, rel=0.08)


def test_cw_demodulator_produces_the_bfo_tone() -> None:
    device = cw_tone(
        offset_hz=CARRIER_OFFSET_HZ,
        center_freq_hz=CENTER_HZ,
        sample_rate_hz=SAMPLE_RATE_HZ,
    )
    device.connect()

    channel = ChannelSpec(CENTER_HZ + CARRIER_OFFSET_HZ, 500.0)
    plan = plan_channelizer(channel.bandwidth_hz, SAMPLE_RATE_HZ, 48_000.0)
    demodulator = CWDemodulator(input_rate_hz=plan.output_rate_hz)

    audio = demodulate_stream(device, demodulator, channel, plan)
    settled = audio[audio.size // 4 :]
    peak_hz = dominant_frequency_hz(settled, demodulator.audio_rate_hz)

    assert demodulator.mode == "CW"
    assert peak_hz == pytest.approx(DEFAULT_BFO_OFFSET_HZ, rel=0.05)


@pytest.mark.parametrize("demod_cls", [NFMDemodulator, USBDemodulator, CWDemodulator])
def test_demodulators_stream_small_blocks_without_large_glitches(demod_cls) -> None:
    if demod_cls is NFMDemodulator:
        device = fm_tone(
            offset_hz=CARRIER_OFFSET_HZ,
            center_freq_hz=CENTER_HZ,
            sample_rate_hz=SAMPLE_RATE_HZ,
        )
        bandwidth_hz = 12_500.0
    elif demod_cls is USBDemodulator:
        device = usb_tone(
            offset_hz=CARRIER_OFFSET_HZ,
            center_freq_hz=CENTER_HZ,
            sample_rate_hz=SAMPLE_RATE_HZ,
        )
        bandwidth_hz = 3_000.0
    else:
        device = cw_tone(
            offset_hz=CARRIER_OFFSET_HZ,
            center_freq_hz=CENTER_HZ,
            sample_rate_hz=SAMPLE_RATE_HZ,
        )
        bandwidth_hz = 500.0

    device.connect()
    channel = ChannelSpec(CENTER_HZ + CARRIER_OFFSET_HZ, bandwidth_hz)
    plan = plan_channelizer(channel.bandwidth_hz, SAMPLE_RATE_HZ, 48_000.0)
    demodulator = demod_cls(input_rate_hz=plan.output_rate_hz)

    chunks = []
    state = None
    for _ in range(24):
        iq = device.read_samples(2_048)
        block, state = channelize(
            iq,
            channel,
            device.center_freq_hz,
            device.sample_rate_hz,
            plan,
            state=state,
        )
        chunks.append(demodulator.process(block))

    audio = np.concatenate(chunks)
    settled = audio[audio.size // 2 :]
    expected_hz = (
        DEFAULT_BFO_OFFSET_HZ if demod_cls is CWDemodulator else AUDIO_FREQ_HZ
    )
    peak_hz = dominant_frequency_hz(settled, demodulator.audio_rate_hz)
    assert peak_hz == pytest.approx(expected_hz, rel=0.08)
