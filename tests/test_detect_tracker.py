"""Unit tests for temporal signal tracking."""

from __future__ import annotations

import pytest

from sdr_console.detect.peaks import DetectedPeak
from sdr_console.detect.tracker import SignalTracker


def _peak(freq_mhz: float, power_db: float) -> DetectedPeak:
    return DetectedPeak(frequency_hz=freq_mhz * 1_000_000.0, power_db=power_db)


def test_signal_not_listed_until_three_consecutive_detections() -> None:
    tracker = SignalTracker(consecutive_hits_required=3)
    signal = _peak(97.0, -20.0)

    tracker.update([signal], timestamp=0.0, capture_gain_db=20.0)
    tracker.update([signal], timestamp=1.0, capture_gain_db=20.0)
    assert tracker.confirmed_signals() == []

    tracker.update([signal], timestamp=2.0, capture_gain_db=20.0)
    confirmed = tracker.confirmed_signals()
    assert len(confirmed) == 1
    assert confirmed[0].frequency_hz == pytest.approx(97_000_000.0)
    assert confirmed[0].power_db == pytest.approx(-20.0)
    assert confirmed[0].capture_gain_db == pytest.approx(20.0)
    assert confirmed[0].detection_count == 1
    assert confirmed[0].confirmed_at == 1


def test_interrupted_candidate_sequence_restarts_confirmation() -> None:
    tracker = SignalTracker(consecutive_hits_required=3)
    signal = _peak(101.5, -18.0)

    tracker.update([signal], timestamp=0.0, capture_gain_db=15.0)
    tracker.update([signal], timestamp=1.0, capture_gain_db=15.0)
    tracker.update([], timestamp=2.0, capture_gain_db=15.0)
    tracker.update([signal], timestamp=3.0, capture_gain_db=15.0)

    assert tracker.confirmed_signals() == []


def test_confirmed_signal_persists_when_no_longer_detected() -> None:
    tracker = SignalTracker(consecutive_hits_required=3)
    signal = _peak(98.0, -25.0)

    for timestamp in (0.0, 1.0, 2.0):
        tracker.update([signal], timestamp=timestamp, capture_gain_db=30.0)

    assert len(tracker.confirmed_signals()) == 1

    for timestamp in (3.0, 4.0, 5.0, 100.0):
        tracker.update([], timestamp=timestamp, capture_gain_db=30.0)

    confirmed = tracker.confirmed_signals()
    assert len(confirmed) == 1
    assert confirmed[0].frequency_hz == pytest.approx(98_000_000.0)


def test_detection_count_increments_without_changing_list_order() -> None:
    tracker = SignalTracker(consecutive_hits_required=3)
    first = _peak(97.0, -20.0)
    second = _peak(100.0, -15.0)

    for timestamp in (0.0, 1.0, 2.0):
        tracker.update([first], timestamp=timestamp, capture_gain_db=10.0)
    for timestamp in (3.0, 4.0, 5.0):
        tracker.update([second], timestamp=timestamp, capture_gain_db=12.0)

    assert tracker.confirmed_signals()[0].frequency_hz == pytest.approx(100_000_000.0)
    assert tracker.confirmed_signals()[1].frequency_hz == pytest.approx(97_000_000.0)

    tracker.update([first], timestamp=6.0, capture_gain_db=10.0)

    confirmed = tracker.confirmed_signals()
    assert confirmed[0].frequency_hz == pytest.approx(100_000_000.0)
    assert confirmed[1].frequency_hz == pytest.approx(97_000_000.0)
    assert confirmed[1].detection_count == 2
    assert confirmed[1].confirmed_at == 1


def test_frequency_drift_updates_same_candidate_and_confirmation() -> None:
    tracker = SignalTracker(consecutive_hits_required=3, match_tolerance_hz=10_000.0)

    tracker.update([_peak(97.000, -22.0)], timestamp=0.0, capture_gain_db=18.0)
    tracker.update([_peak(97.003, -21.0)], timestamp=1.0, capture_gain_db=18.0)
    tracker.update([_peak(97.001, -20.5)], timestamp=2.0, capture_gain_db=18.0)

    confirmed = tracker.confirmed_signals()
    assert len(confirmed) == 1
    assert confirmed[0].frequency_hz == pytest.approx(97_001_000.0, rel=1e-6)
    assert confirmed[0].power_db == pytest.approx(-20.5)


def test_clear_all_removes_confirmed_and_candidate_tracks() -> None:
    tracker = SignalTracker(consecutive_hits_required=3)
    signal = _peak(96.0, -20.0)

    tracker.update([signal], timestamp=0.0, capture_gain_db=20.0)
    tracker.update([signal], timestamp=1.0, capture_gain_db=20.0)
    tracker.clear_all()

    assert tracker.confirmed_signals() == []
    tracker.update([signal], timestamp=2.0, capture_gain_db=20.0)
    assert tracker.confirmed_signals() == []


def test_remove_confirmed_signal_allows_reconfirmation_from_scratch() -> None:
    tracker = SignalTracker(consecutive_hits_required=3)
    signal = _peak(95.0, -18.0)

    for timestamp in (0.0, 1.0, 2.0):
        tracker.update([signal], timestamp=timestamp, capture_gain_db=25.0)
    assert len(tracker.confirmed_signals()) == 1

    assert tracker.remove(95_000_000.0)
    assert tracker.confirmed_signals() == []

    tracker.update([signal], timestamp=3.0, capture_gain_db=25.0)
    tracker.update([signal], timestamp=4.0, capture_gain_db=25.0)
    assert tracker.confirmed_signals() == []

    tracker.update([signal], timestamp=5.0, capture_gain_db=25.0)
    confirmed = tracker.confirmed_signals()
    assert len(confirmed) == 1
    assert confirmed[0].confirmed_at == 2


def test_reset_candidates_keeps_confirmed_signals() -> None:
    tracker = SignalTracker(consecutive_hits_required=3)
    confirmed_signal = _peak(99.0, -20.0)
    candidate_signal = _peak(101.0, -30.0)

    for timestamp in (0.0, 1.0, 2.0):
        tracker.update([confirmed_signal], timestamp=timestamp, capture_gain_db=20.0)
    tracker.update([candidate_signal], timestamp=3.0, capture_gain_db=20.0)

    tracker.reset_candidates()

    assert len(tracker.confirmed_signals()) == 1
    tracker.update([candidate_signal], timestamp=4.0, capture_gain_db=20.0)
    assert tracker.confirmed_signals()[0].detection_count == 1


def test_capture_gain_db_is_fixed_at_confirmation() -> None:
    tracker = SignalTracker(consecutive_hits_required=3)
    signal = _peak(97.0, -20.0)

    for timestamp in (0.0, 1.0, 2.0):
        tracker.update([signal], timestamp=timestamp, capture_gain_db=20.0)

    tracker.update([signal], timestamp=3.0, capture_gain_db=35.0)

    confirmed = tracker.confirmed_signals()
    assert len(confirmed) == 1
    assert confirmed[0].capture_gain_db == pytest.approx(20.0)


def test_confirm_directly_skips_candidate_stage() -> None:
    tracker = SignalTracker(consecutive_hits_required=3)
    signal = _peak(104.0, -18.0)

    tracker.confirm_directly([signal], capture_gain_db=12.0)

    confirmed = tracker.confirmed_signals()
    assert len(confirmed) == 1
    assert confirmed[0].frequency_hz == pytest.approx(104_000_000.0)
    assert confirmed[0].capture_gain_db == pytest.approx(12.0)


def test_confirm_directly_updates_existing_confirmed_match() -> None:
    tracker = SignalTracker(consecutive_hits_required=3, match_tolerance_hz=10_000.0)
    first = _peak(88.0, -20.0)
    updated = _peak(88.005, -15.0)

    tracker.confirm_directly([first], capture_gain_db=10.0)
    tracker.confirm_directly([updated], capture_gain_db=10.0)

    confirmed = tracker.confirmed_signals()
    assert len(confirmed) == 1
    assert confirmed[0].frequency_hz == pytest.approx(88_005_000.0)
    assert confirmed[0].power_db == pytest.approx(-15.0)
    assert confirmed[0].detection_count == 2


def test_compact_confirmed_merges_wideband_skirt_detections() -> None:
    """Regression: one W-FM station should not appear as many adjacent rows."""
    tracker = SignalTracker(consecutive_hits_required=1, match_tolerance_hz=5_000.0)
    screenshot_mhz = (
        98.964,
        98.980,
        98.984,
        99.002,
        99.004,
        99.008,
        99.016,
        99.026,
    )
    for freq_mhz in screenshot_mhz:
        tracker.confirm_directly(
            [_peak(freq_mhz, -39.0)],
            capture_gain_db=41.0,
            match_tolerance_hz=1_000.0,
        )

    assert len(tracker.confirmed_signals()) == len(screenshot_mhz)

    tracker.compact_confirmed(merge_bandwidth_hz=50_000.0)
    confirmed = tracker.confirmed_signals()
    assert len(confirmed) == 1
    assert 98_964_000.0 <= confirmed[0].frequency_hz <= 99_026_000.0
    assert confirmed[0].detection_count == len(screenshot_mhz)


def test_compact_confirmed_preserves_existing_list_order() -> None:
    tracker = SignalTracker(consecutive_hits_required=1, match_tolerance_hz=5_000.0)
    top = _peak(104.0, -10.0)
    merge_a = _peak(98.980, -20.0)
    merge_b = _peak(99.002, -18.0)

    tracker.confirm_directly([top], capture_gain_db=10.0)
    tracker.confirm_directly([merge_a], capture_gain_db=10.0)
    tracker.confirm_directly([merge_b], capture_gain_db=10.0)

    assert [item.frequency_hz for item in tracker.confirmed_signals()] == [
        pytest.approx(99_002_000.0),
        pytest.approx(98_980_000.0),
        pytest.approx(104_000_000.0),
    ]

    tracker.compact_confirmed(merge_bandwidth_hz=50_000.0)
    confirmed = tracker.confirmed_signals()
    assert len(confirmed) == 2
    assert 98_980_000.0 <= confirmed[0].frequency_hz <= 99_002_000.0
    assert confirmed[1].frequency_hz == pytest.approx(104_000_000.0)


def test_compact_keeps_remerged_signal_at_original_list_position() -> None:
    from sdr_console.detect.tracker import _ConfirmedTrack

    tracker = SignalTracker(consecutive_hits_required=1, match_tolerance_hz=1_000.0)
    tracker.confirm_directly([_peak(97.0, -20.0)], capture_gain_db=10.0)
    tracker.confirm_directly([_peak(100.0, -15.0)], capture_gain_db=10.0)
    assert tracker.confirmed_signals()[0].frequency_hz == pytest.approx(100_000_000.0)
    assert tracker.confirmed_signals()[1].frequency_hz == pytest.approx(97_000_000.0)

    tracker._confirmed.insert(
        0,
        _ConfirmedTrack(
            frequency_hz=97_050_000.0,
            power_db=-18.0,
            capture_gain_db=10.0,
            detection_count=1,
            confirmed_at=tracker._next_confirmed_at,
        ),
    )
    tracker._next_confirmed_at += 1

    tracker.compact_confirmed(merge_bandwidth_hz=100_000.0)
    confirmed = tracker.confirmed_signals()
    assert len(confirmed) == 2
    assert confirmed[0].frequency_hz == pytest.approx(100_000_000.0)
    assert confirmed[1].frequency_hz == pytest.approx(97_050_000.0)
    assert confirmed[1].detection_count == 2


def test_tracker_rejects_invalid_configuration() -> None:
    with pytest.raises(ValueError, match="consecutive_hits_required"):
        SignalTracker(consecutive_hits_required=0)

    with pytest.raises(ValueError, match="match_tolerance_hz"):
        SignalTracker(match_tolerance_hz=0.0)
