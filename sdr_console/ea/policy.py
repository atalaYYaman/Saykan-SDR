"""Karıştırma isteği doğrulama — onay, yetkili pencere, tavanlar."""

from __future__ import annotations

from dataclasses import dataclass

from sdr_console.ea.constants import (
    MAX_JAM_DURATION_S,
    MIN_JAM_ATTENUATION_DB,
    MIN_JAM_BANDWIDTH_HZ,
    MIN_JAM_DURATION_S,
)
from sdr_console.ea.errors import (
    JamNotAuthorizedError,
    JamNotConfirmedError,
    JamPolicyError,
)
from sdr_console.tx.waveform import clamp_bandwidth_hz


@dataclass(frozen=True)
class JamParams:
    """Doğrulanmış baraj yayını parametreleri."""

    freq_hz: float
    bandwidth_hz: float
    attenuation_db: float
    duration_s: float


def validate_jam_request(
    *,
    freq_hz: float,
    bandwidth_hz: float,
    attenuation_db: float,
    duration_s: float,
    sample_rate_hz: float,
    confirmed: bool,
    authorized_window: bool,
) -> JamParams:
    """Onay ve tavanları uygula; ihlalde istisna fırlat (sessizce kısma)."""
    if not confirmed:
        raise JamNotConfirmedError(
            "Karıştırma yayını açık operatör onayı ister. "
            "confirmed=True yalnızca onay diyaloğundan sonra."
        )
    if not authorized_window:
        raise JamNotAuthorizedError(
            "Yetkili test penceresi onaylanmadan karıştırma başlatılamaz."
        )

    freq = float(freq_hz)
    if freq <= 0.0:
        raise JamPolicyError("freq_hz must be positive")

    try:
        occupied = clamp_bandwidth_hz(float(bandwidth_hz), float(sample_rate_hz))
    except ValueError as exc:
        raise JamPolicyError(str(exc)) from exc
    if occupied < MIN_JAM_BANDWIDTH_HZ:
        raise JamPolicyError(
            f"bandwidth_hz must be at least {MIN_JAM_BANDWIDTH_HZ:.0f} Hz"
        )

    att = float(attenuation_db)
    if att < MIN_JAM_ATTENUATION_DB:
        raise JamPolicyError(
            f"attenuation_db {att:.1f} dB jam tabanının altında "
            f"(minimum {MIN_JAM_ATTENUATION_DB:.1f} dB)."
        )

    duration = float(duration_s)
    if duration <= 0.0:
        raise JamPolicyError("duration_s must be positive")
    if duration < MIN_JAM_DURATION_S:
        raise JamPolicyError(
            f"duration_s {duration:.2f} s jam alt sınırının altında "
            f"(minimum {MIN_JAM_DURATION_S:.2f} s)."
        )
    if duration > MAX_JAM_DURATION_S:
        raise JamPolicyError(
            f"duration_s {duration:.2f} s jam tavanını aşıyor "
            f"(en fazla {MAX_JAM_DURATION_S:.0f} s)."
        )

    return JamParams(
        freq_hz=freq,
        bandwidth_hz=occupied,
        attenuation_db=att,
        duration_s=duration,
    )
