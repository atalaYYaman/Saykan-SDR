"""ReplaySession IQ biriktirme ve yakalama özeti."""

from __future__ import annotations

import numpy as np

from sdr_console.tx.ook_encoder import encode_ook
from sdr_console.tx.session import ReplaySession, format_capture_summary

SAMPLE_RATE_HZ = 2_000_000.0
BIT_DURATION_S = 0.0003


def test_ingest_finishes_when_enough_samples_collected() -> None:
    session = ReplaySession()
    iq = encode_ook([1, 0, 1], BIT_DURATION_S, SAMPLE_RATE_HZ, 0.85)
    session.begin_capture(iq.size)

    assert not session.ingest_block(iq[: iq.size // 2])
    assert session.ingest_block(iq[iq.size // 2 :])

    capture, assessment = session.finish_capture(SAMPLE_RATE_HZ)
    assert capture.bits is not None
    assert list(capture.bits) == [1, 0, 1]
    assert assessment.capture_count == 1
    assert "darbe" in format_capture_summary(capture)


def test_ingest_copies_blocks_so_source_mutation_is_ignored() -> None:
    session = ReplaySession()
    block = np.ones(32, dtype=np.complex64)
    session.begin_capture(32)
    session.ingest_block(block)
    block[:] = 0
    capture, _ = session.finish_capture(SAMPLE_RATE_HZ)
    assert capture.pulses
    assert any(pulse.level for pulse in capture.pulses)


def test_clear_resets_captures() -> None:
    session = ReplaySession()
    iq = encode_ook([1, 0], BIT_DURATION_S, SAMPLE_RATE_HZ, 0.85)
    session.begin_capture(iq.size)
    session.ingest_block(iq)
    session.finish_capture(SAMPLE_RATE_HZ)
    assert session.latest is not None

    session.clear()
    assert session.latest is None
    assert session.captures == []
