"""End-to-end AM demodulation tests against a mock AM transmitter.

No speaker involved: the demodulated array is compared with the audio tone that
was modulated onto the mock carrier.
"""

from __future__ import annotations

import numpy as np
import pytest

from sdr_console.demod.am import AMDemodulator
from sdr_console.demod.base import Demodulator
from sdr_console.dsp.channel import ChannelSpec
from sdr_console.dsp.channelizer import ChannelizedBlock, channelize, plan_channelizer
from sdr_console.hal.scenarios import AMMockDevice, AMSignalSpec, am_tone

CENTER_HZ = 100_000_000.0
SAMPLE_RATE_HZ = 2_048_000.0
CARRIER_OFFSET_HZ = 50_000.0
AUDIO_FREQ_HZ = 1_000.0
CHANNEL_BANDWIDTH_HZ = 10_000.0
BLOCK = 32_768


def dominant_frequency_hz(audio: np.ndarray, audio_rate_hz: float) -> float:
    """Frequency of the strongest non-DC component of an audio block."""
    spectrum = np.abs(np.fft.rfft(audio * np.hanning(audio.size)))
    freqs = np.fft.rfftfreq(audio.size, d=1.0 / audio_rate_hz)
    spectrum[freqs < 20.0] = 0.0
    return float(freqs[int(np.argmax(spectrum))])


def demodulate_stream(
    device: AMMockDevice,
    demodulator: Demodulator,
    channel: ChannelSpec,
    plan,
    num_blocks: int,
    block_size: int = BLOCK,
) -> np.ndarray:
    """Read from the device and run the full channelize + demodulate chain."""
    audio_chunks = []
    state = None
    for _ in range(num_blocks):
        iq = device.read_samples(block_size)
        block, state = channelize(
            iq,
            channel,
            device.center_freq_hz,
            device.sample_rate_hz,
            plan,
            state=state,
        )
        audio_chunks.append(demodulator.process(block))
    return np.concatenate(audio_chunks)


@pytest.fixture
def am_device() -> AMMockDevice:
    device = am_tone(
        offset_hz=CARRIER_OFFSET_HZ,
        audio_freq_hz=AUDIO_FREQ_HZ,
        modulation_index=0.5,
        center_freq_hz=CENTER_HZ,
        sample_rate_hz=SAMPLE_RATE_HZ,
    )
    device.connect()
    return device


@pytest.fixture
def channel() -> ChannelSpec:
    return ChannelSpec(CENTER_HZ + CARRIER_OFFSET_HZ, CHANNEL_BANDWIDTH_HZ)


@pytest.fixture
def plan(channel: ChannelSpec):
    return plan_channelizer(channel.bandwidth_hz, SAMPLE_RATE_HZ, 48_000.0)


@pytest.fixture
def demodulator(plan) -> AMDemodulator:
    return AMDemodulator(input_rate_hz=plan.output_rate_hz)


def test_mock_am_envelope_matches_the_modulation_index(am_device: AMMockDevice) -> None:
    iq = am_device.read_samples(BLOCK)
    envelope = np.abs(iq)

    # Envelope swings between amplitude * (1 -+ modulation_index).
    spec = am_device.am
    assert envelope.max() == pytest.approx(
        spec.relative_amplitude * (1.0 + spec.modulation_index), abs=0.01
    )
    assert envelope.min() == pytest.approx(
        spec.relative_amplitude * (1.0 - spec.modulation_index), abs=0.01
    )


def test_mock_am_is_phase_continuous_across_reads(am_device: AMMockDevice) -> None:
    first = am_device.read_samples(1024)
    second = am_device.read_samples(1024)
    joined = np.abs(np.concatenate([first, second]))

    # A discontinuity would show up as a jump much larger than the smooth
    # sample-to-sample change of a 1 kHz envelope at 2.048 Msps.
    steps = np.abs(np.diff(joined))
    assert steps.max() < 10.0 * float(np.median(steps)) + 1e-3


def test_mock_am_out_of_band_carrier_is_not_visible() -> None:
    device = AMMockDevice(
        am=AMSignalSpec(carrier_freq_hz=CENTER_HZ + 5_000_000.0),
        center_freq_hz=CENTER_HZ,
        sample_rate_hz=SAMPLE_RATE_HZ,
        noise_amplitude=0.01,
    )
    device.connect()

    envelope = np.abs(device.read_samples(4096))

    assert envelope.mean() < 0.1


def test_demodulator_reports_its_rates(demodulator: AMDemodulator, plan) -> None:
    assert demodulator.mode == "AM"
    assert AMDemodulator.MODE == "AM"
    assert AMDemodulator.DEFAULT_BANDWIDTH_HZ == 10_000.0
    assert demodulator.input_rate_hz == plan.output_rate_hz
    assert demodulator.audio_rate_hz == pytest.approx(
        plan.output_rate_hz / demodulator.decimation
    )


def test_demodulated_audio_is_the_modulating_tone(
    am_device: AMMockDevice,
    demodulator: AMDemodulator,
    channel: ChannelSpec,
    plan,
) -> None:
    audio = demodulate_stream(am_device, demodulator, channel, plan, num_blocks=4)

    # Skip filter warm-up before measuring.
    settled = audio[audio.size // 4 :]
    peak_hz = dominant_frequency_hz(settled, demodulator.audio_rate_hz)

    assert audio.dtype == np.float32
    assert peak_hz == pytest.approx(AUDIO_FREQ_HZ, rel=0.05)
    assert np.all(np.abs(audio) <= 1.0)


def test_demodulated_audio_has_no_dc_offset(
    am_device: AMMockDevice,
    demodulator: AMDemodulator,
    channel: ChannelSpec,
    plan,
) -> None:
    audio = demodulate_stream(am_device, demodulator, channel, plan, num_blocks=4)
    settled = audio[audio.size // 4 :]

    # Envelope detection turns the carrier into a large DC term (0.8 here); after
    # the blocker only a fraction of the tone's own level may remain. The window
    # never holds a whole number of cycles, so the tone leaks a little into the
    # mean too - hence a threshold relative to RMS rather than an exact zero.
    rms = float(np.sqrt(np.mean(np.square(settled))))
    assert abs(float(np.mean(settled))) < 0.05 * rms


def test_audio_amplitude_tracks_the_modulation_index(
    channel: ChannelSpec,
    plan,
) -> None:
    amplitudes = {}
    for modulation_index in (0.25, 0.5):
        device = am_tone(
            offset_hz=CARRIER_OFFSET_HZ,
            audio_freq_hz=AUDIO_FREQ_HZ,
            modulation_index=modulation_index,
            center_freq_hz=CENTER_HZ,
            sample_rate_hz=SAMPLE_RATE_HZ,
        )
        device.connect()
        demodulator = AMDemodulator(
            input_rate_hz=plan.output_rate_hz,
            agc_enabled=False,
        )
        audio = demodulate_stream(device, demodulator, channel, plan, num_blocks=4)
        amplitudes[modulation_index] = float(np.max(np.abs(audio[audio.size // 2 :])))

    # Envelope AC amplitude is amplitude * modulation_index, so doubling the
    # index doubles the audio.
    assert amplitudes[0.5] == pytest.approx(2.0 * amplitudes[0.25], rel=0.1)


def test_streaming_in_small_blocks_stays_continuous(
    am_device: AMMockDevice,
    channel: ChannelSpec,
    plan,
) -> None:
    small = AMDemodulator(input_rate_hz=plan.output_rate_hz)
    audio = demodulate_stream(
        am_device, small, channel, plan, num_blocks=32, block_size=2_048
    )
    settled = audio[audio.size // 2 :]

    peak_hz = dominant_frequency_hz(settled, small.audio_rate_hz)
    steps = np.abs(np.diff(settled))

    assert peak_hz == pytest.approx(AUDIO_FREQ_HZ, rel=0.05)
    # No click at block seams: every step stays near the smooth tone slope.
    assert steps.max() < 5.0 * float(np.median(steps))


def test_reset_clears_carried_over_state(
    am_device: AMMockDevice,
    demodulator: AMDemodulator,
    channel: ChannelSpec,
    plan,
) -> None:
    demodulate_stream(am_device, demodulator, channel, plan, num_blocks=1)
    demodulator.reset()

    assert demodulator._dc_state is None
    assert demodulator._audio_state is None
    assert demodulator._audio_offset == 0


def test_process_rejects_a_mismatched_block_rate(demodulator: AMDemodulator) -> None:
    block = ChannelizedBlock(
        samples=np.ones(128, dtype=np.complex64),
        sample_rate_hz=demodulator.input_rate_hz * 2.0,
    )

    with pytest.raises(ValueError, match="does not match"):
        demodulator.process(block)


def test_process_accepts_an_empty_block(demodulator: AMDemodulator) -> None:
    block = ChannelizedBlock(
        samples=np.zeros(0, dtype=np.complex64),
        sample_rate_hz=demodulator.input_rate_hz,
    )

    audio = demodulator.process(block)

    assert audio.size == 0
    assert audio.dtype == np.float32
