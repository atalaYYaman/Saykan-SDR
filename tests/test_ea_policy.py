"""Karıştırma politikası — onay, yetkili pencere, tavanlar."""

from __future__ import annotations

import pytest

from sdr_console.ea.constants import (
    MAX_JAM_DURATION_S,
    MIN_JAM_ATTENUATION_DB,
    MIN_JAM_BANDWIDTH_HZ,
)
from sdr_console.ea.errors import (
    JamNotAuthorizedError,
    JamNotConfirmedError,
    JamPolicyError,
)
from sdr_console.ea.policy import validate_jam_request

_RATE = 2_048_000.0


def _valid(**overrides: object) -> dict[str, object]:
    params: dict[str, object] = {
        "freq_hz": 433_970_000.0,
        "bandwidth_hz": 2_048_000.0,
        "attenuation_db": MIN_JAM_ATTENUATION_DB,
        "duration_s": 5.0,
        "sample_rate_hz": _RATE,
        "confirmed": True,
        "authorized_window": True,
    }
    params.update(overrides)
    return params


def test_valid_request_returns_params() -> None:
    params = validate_jam_request(**_valid())
    assert params.freq_hz == pytest.approx(433_970_000.0)
    assert params.attenuation_db == pytest.approx(MIN_JAM_ATTENUATION_DB)
    assert params.duration_s == pytest.approx(5.0)
    assert params.bandwidth_hz == pytest.approx(_RATE)


def test_unconfirmed_is_rejected() -> None:
    with pytest.raises(JamNotConfirmedError, match="onay"):
        validate_jam_request(**_valid(confirmed=False))


def test_unauthorized_window_is_rejected() -> None:
    with pytest.raises(JamNotAuthorizedError, match="Yetkili"):
        validate_jam_request(**_valid(authorized_window=False))


def test_attenuation_below_jam_floor_is_rejected() -> None:
    with pytest.raises(JamPolicyError, match="taban"):
        validate_jam_request(**_valid(attenuation_db=MIN_JAM_ATTENUATION_DB - 1.0))


def test_duration_above_ceiling_is_rejected() -> None:
    with pytest.raises(JamPolicyError, match="tavan"):
        validate_jam_request(**_valid(duration_s=MAX_JAM_DURATION_S + 1.0))


def test_bandwidth_below_floor_is_rejected() -> None:
    with pytest.raises(JamPolicyError, match="bandwidth"):
        validate_jam_request(**_valid(bandwidth_hz=MIN_JAM_BANDWIDTH_HZ - 1_000.0))
