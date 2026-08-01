"""Audio output error types."""

from __future__ import annotations


class AudioError(Exception):
    """Base class for audio output failures."""


class AudioUnavailableError(AudioError):
    """The audio backend or output device cannot be used."""
