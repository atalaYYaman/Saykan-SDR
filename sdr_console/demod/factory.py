"""Map mode labels to demodulator classes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sdr_console.demod.am import AMDemodulator
from sdr_console.demod.base import Demodulator
from sdr_console.demod.cw import CWDemodulator
from sdr_console.demod.fm import NFMDemodulator, WFMDemodulator
from sdr_console.demod.ssb import LSBDemodulator, USBDemodulator

DemodulatorFactory = Callable[[float, int], Demodulator]

DEMOD_MODES: tuple[str, ...] = ("AM", "N-FM", "W-FM", "USB", "LSB", "CW")

_DEMOD_BY_MODE: dict[str, type[Demodulator]] = {
    AMDemodulator.MODE: AMDemodulator,
    NFMDemodulator.MODE: NFMDemodulator,
    WFMDemodulator.MODE: WFMDemodulator,
    USBDemodulator.MODE: USBDemodulator,
    LSBDemodulator.MODE: LSBDemodulator,
    CWDemodulator.MODE: CWDemodulator,
}


def is_known_demod_mode(mode: str) -> bool:
    return mode in _DEMOD_BY_MODE


def demodulator_class(mode: str) -> type[Demodulator]:
    """Return the demodulator class for ``mode``.

    Raises:
        ValueError: When ``mode`` is not registered.
    """
    try:
        return _DEMOD_BY_MODE[mode]
    except KeyError as exc:
        known = ", ".join(DEMOD_MODES)
        raise ValueError(f"Unsupported demod mode {mode!r} (known: {known})") from exc


def default_bandwidth_hz(mode: str) -> float:
    """Suggested channel bandwidth when the user picks ``mode``."""
    return float(demodulator_class(mode).DEFAULT_BANDWIDTH_HZ)


def create_demodulator(
    mode: str,
    input_rate_hz: float,
    audio_decimation: int,
    **kwargs: Any,
) -> Demodulator:
    """Build a demodulator for ``mode`` at the given IF and audio decimation."""
    cls = demodulator_class(mode)
    return cls(
        input_rate_hz=input_rate_hz,
        audio_decimation=audio_decimation,
        **kwargs,
    )


def demodulator_factory(mode: str) -> DemodulatorFactory:
    """Return a ``DemodWorker``-compatible factory bound to ``mode``."""

    def factory(input_rate_hz: float, audio_decimation: int) -> Demodulator:
        return create_demodulator(mode, input_rate_hz, audio_decimation)

    return factory


def default_demodulator_factory(
    input_rate_hz: float,
    audio_decimation: int,
) -> Demodulator:
    """Default worker factory — AM until the UI selects another mode."""
    return create_demodulator(AMDemodulator.MODE, input_rate_hz, audio_decimation)
