"""Audio output layer — plays demodulated audio on the sound card."""

from sdr_console.audio.errors import AudioError, AudioUnavailableError
from sdr_console.audio.sink import (
    DEFAULT_BLOCK_SIZE,
    DEFAULT_VOLUME,
    AudioBlockSource,
    AudioSink,
    NullAudioSink,
    QueuePullSink,
    SoundDeviceAudioSink,
    sounddevice_available,
)

__all__ = [
    "DEFAULT_BLOCK_SIZE",
    "DEFAULT_VOLUME",
    "AudioBlockSource",
    "AudioError",
    "AudioSink",
    "AudioUnavailableError",
    "NullAudioSink",
    "QueuePullSink",
    "SoundDeviceAudioSink",
    "sounddevice_available",
]
