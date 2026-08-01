"""Demodulation — baseband channel blocks to mono audio."""

from sdr_console.demod.am import AMDemodulator
from sdr_console.demod.base import Demodulator

__all__ = [
    "AMDemodulator",
    "Demodulator",
]
