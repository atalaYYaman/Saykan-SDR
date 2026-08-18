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

# Mode → default RF channel bandwidth (RFBW). Owned here (not dsp/) so the
# DSP layer stays mode-agnostic; values live on each Demodulator class.
DEFAULT_RFBW_HZ: dict[str, float] = {
    mode: float(cls.DEFAULT_BANDWIDTH_HZ) for mode, cls in _DEMOD_BY_MODE.items()
}

# Mode → default audio low-pass cutoff (AFBW).
DEFAULT_AFBW_HZ: dict[str, float] = {
    mode: float(cls.DEFAULT_AFBW_HZ) for mode, cls in _DEMOD_BY_MODE.items()
}

# Mode → default AGC enable / preset.
DEFAULT_AGC_ENABLED: dict[str, bool] = {
    mode: bool(cls.DEFAULT_AGC_ENABLED) for mode, cls in _DEMOD_BY_MODE.items()
}
DEFAULT_AGC_PRESET: dict[str, str] = {
    mode: str(cls.DEFAULT_AGC_PRESET.value) for mode, cls in _DEMOD_BY_MODE.items()
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
    """Suggested RF channel bandwidth (RFBW) when the user picks ``mode``.

    Defaults: AM 10 kHz, N-FM 12.5 kHz, USB/LSB 2.7 kHz, W-FM 200 kHz, CW 500 Hz.
    """
    return DEFAULT_RFBW_HZ[demodulator_class(mode).MODE]


def default_afbw_hz(mode: str) -> float:
    """Suggested audio bandwidth (AFBW) when the user picks ``mode``.

    Defaults: AM/N-FM 4 kHz, USB/LSB 3 kHz, W-FM 15 kHz, CW 1 kHz.
    """
    return DEFAULT_AFBW_HZ[demodulator_class(mode).MODE]


def default_agc_enabled(mode: str) -> bool:
    """Whether AGC is on by default for ``mode``."""
    return DEFAULT_AGC_ENABLED[demodulator_class(mode).MODE]


def default_agc_preset(mode: str) -> str:
    """Default AGC preset name for ``mode`` (fast/slow/hang/limiter)."""
    return DEFAULT_AGC_PRESET[demodulator_class(mode).MODE]


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


def demodulator_factory(
    mode: str,
    *,
    deemphasis_tau_s: float | None = None,
    nfm_deemphasis: bool = False,
    afbw_hz: float | None = None,
    agc_enabled: bool | None = None,
    agc_preset: str | None = None,
) -> DemodulatorFactory:
    """Return a ``DemodWorker``-compatible factory bound to ``mode``.

    Args:
        deemphasis_tau_s: FM de-emphasis time constant (50e-6 or 75e-6).
            Applied always for W-FM; for N-FM only when ``nfm_deemphasis``.
        nfm_deemphasis: Enable optional N-FM de-emphasis.
        afbw_hz: Audio low-pass cutoff; ``None`` uses the mode default.
        agc_enabled: Override AGC on/off; ``None`` uses the mode default.
        agc_preset: Override AGC profile name; ``None`` uses the mode default.
    """

    def factory(input_rate_hz: float, audio_decimation: int) -> Demodulator:
        kwargs: dict[str, Any] = {}
        if afbw_hz is not None:
            kwargs["afbw_hz"] = afbw_hz
        if agc_enabled is not None:
            kwargs["agc_enabled"] = agc_enabled
        if agc_preset is not None:
            kwargs["agc_preset"] = agc_preset
        if mode == WFMDemodulator.MODE:
            kwargs["deemphasis"] = True
            if deemphasis_tau_s is not None:
                kwargs["deemphasis_tau_s"] = deemphasis_tau_s
        elif mode == NFMDemodulator.MODE:
            kwargs["deemphasis"] = nfm_deemphasis
            if nfm_deemphasis and deemphasis_tau_s is not None:
                kwargs["deemphasis_tau_s"] = deemphasis_tau_s
        return create_demodulator(mode, input_rate_hz, audio_decimation, **kwargs)

    return factory


def default_demodulator_factory(
    input_rate_hz: float,
    audio_decimation: int,
) -> Demodulator:
    """Default worker factory — AM until the UI selects another mode."""
    return create_demodulator(AMDemodulator.MODE, input_rate_hz, audio_decimation)
