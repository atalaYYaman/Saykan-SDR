"""Temporal filtering and persistence for detected spectrum peaks."""

from __future__ import annotations

from dataclasses import dataclass

from sdr_console.detect.detected_signal import DetectedSignal
from sdr_console.detect.peaks import DEFAULT_MERGE_BANDWIDTH_HZ, DetectedPeak


@dataclass
class _CandidateTrack:
    """A frequency seen in the current band but not yet confirmed."""

    frequency_hz: float
    power_db: float
    consecutive_hits: int = 1


@dataclass
class _ConfirmedTrack:
    """A confirmed signal kept until explicitly removed."""

    frequency_hz: float
    power_db: float
    capture_gain_db: float
    detection_count: int
    confirmed_at: int


class SignalTracker:
    """Track candidate peaks and promote them to session-persistent confirmations.

    A frequency must be detected in ``consecutive_hits_required`` consecutive
    frames before it appears in :meth:`confirmed_signals`. Confirmed entries stay
    in the list until :meth:`clear_all` or :meth:`remove` is called, even if the
    signal later disappears from the spectrum.
    """

    def __init__(
        self,
        *,
        consecutive_hits_required: int = 3,
        match_tolerance_hz: float = DEFAULT_MERGE_BANDWIDTH_HZ,
    ) -> None:
        if consecutive_hits_required < 1:
            raise ValueError("consecutive_hits_required must be at least 1")
        if match_tolerance_hz <= 0.0:
            raise ValueError("match_tolerance_hz must be positive")

        self._consecutive_hits_required = consecutive_hits_required
        self._match_tolerance_hz = match_tolerance_hz
        self._candidates: list[_CandidateTrack] = []
        self._confirmed: list[_ConfirmedTrack] = []
        self._next_confirmed_at = 1

    @property
    def consecutive_hits_required(self) -> int:
        return self._consecutive_hits_required

    @property
    def match_tolerance_hz(self) -> float:
        return self._match_tolerance_hz

    def set_match_tolerance_hz(self, match_tolerance_hz: float) -> None:
        if match_tolerance_hz <= 0.0:
            raise ValueError("match_tolerance_hz must be positive")
        self._match_tolerance_hz = match_tolerance_hz

    def compact_confirmed(self, merge_bandwidth_hz: float) -> None:
        """Merge confirmed tracks closer than ``merge_bandwidth_hz`` into one row each."""
        if merge_bandwidth_hz <= 0.0:
            raise ValueError("merge_bandwidth_hz must be positive")
        if len(self._confirmed) < 2:
            return

        original_index = {id(track): index for index, track in enumerate(self._confirmed)}
        sorted_tracks = sorted(self._confirmed, key=lambda track: track.frequency_hz)
        clusters: list[list[_ConfirmedTrack]] = [[sorted_tracks[0]]]

        for track in sorted_tracks[1:]:
            cluster_end_hz = max(item.frequency_hz for item in clusters[-1])
            if track.frequency_hz - cluster_end_hz < merge_bandwidth_hz:
                clusters[-1].append(track)
            else:
                clusters.append([track])

        compacted: list[_ConfirmedTrack] = []
        cluster_positions: list[int] = []
        for cluster in clusters:
            strongest = max(cluster, key=lambda item: item.power_db)
            earliest = min(cluster, key=lambda item: item.confirmed_at)
            compacted.append(
                _ConfirmedTrack(
                    frequency_hz=strongest.frequency_hz,
                    power_db=strongest.power_db,
                    capture_gain_db=earliest.capture_gain_db,
                    detection_count=sum(item.detection_count for item in cluster),
                    confirmed_at=earliest.confirmed_at,
                )
            )
            cluster_positions.append(
                original_index[id(min(cluster, key=lambda item: item.confirmed_at))]
            )

        self._confirmed = [
            track
            for _, track in sorted(
                zip(cluster_positions, compacted),
                key=lambda pair: pair[0],
            )
        ]

    def reset_candidates(self) -> None:
        """Drop in-progress candidate tracks without touching confirmed signals."""
        self._candidates.clear()

    def reset(self) -> None:
        """Alias for :meth:`reset_candidates`."""
        self.reset_candidates()

    def clear_all(self) -> None:
        """Remove every confirmed and candidate track."""
        self._candidates.clear()
        self._confirmed.clear()

    def remove(self, frequency_hz: float) -> bool:
        """Remove the confirmed or candidate track nearest ``frequency_hz``."""
        removed = self._remove_from_list(self._confirmed, frequency_hz)
        if self._remove_from_list(self._candidates, frequency_hz):
            removed = True
        return removed

    def update(
        self,
        peaks: list[DetectedPeak],
        timestamp: float,
        *,
        capture_gain_db: float = 0.0,
    ) -> None:
        """Ingest one frame of detections at ``timestamp`` seconds."""
        del timestamp  # reserved for future diagnostics; ordering uses confirmed_at
        matched_peak_indices: set[int] = set()

        for confirmed in self._confirmed:
            peak_index = self._find_matching_peak(
                peaks,
                matched_peak_indices,
                confirmed.frequency_hz,
            )
            if peak_index is None:
                continue

            peak = peaks[peak_index]
            confirmed.frequency_hz = peak.frequency_hz
            confirmed.power_db = peak.power_db
            confirmed.detection_count += 1
            matched_peak_indices.add(peak_index)

        remaining_candidates: list[_CandidateTrack] = []
        for candidate in self._candidates:
            peak_index = self._find_matching_peak(
                peaks,
                matched_peak_indices,
                candidate.frequency_hz,
            )
            if peak_index is None:
                continue

            peak = peaks[peak_index]
            candidate.frequency_hz = peak.frequency_hz
            candidate.power_db = peak.power_db
            candidate.consecutive_hits += 1
            matched_peak_indices.add(peak_index)

            if candidate.consecutive_hits >= self._consecutive_hits_required:
                self._promote_candidate(candidate, capture_gain_db)
            else:
                remaining_candidates.append(candidate)

        self._candidates = remaining_candidates

        for peak_index, peak in enumerate(peaks):
            if peak_index in matched_peak_indices:
                continue

            existing = self._find_matching_confirmed(peak.frequency_hz)
            if existing is not None:
                existing.frequency_hz = peak.frequency_hz
                existing.power_db = peak.power_db
                existing.detection_count += 1
                matched_peak_indices.add(peak_index)
                continue

            candidate = _CandidateTrack(
                frequency_hz=peak.frequency_hz,
                power_db=peak.power_db,
                consecutive_hits=1,
            )
            if candidate.consecutive_hits >= self._consecutive_hits_required:
                self._promote_candidate(candidate, capture_gain_db)
            else:
                self._candidates.append(candidate)

    def confirmed_signals(self) -> list[DetectedSignal]:
        """Return confirmed signals in stable display order (newest confirmations first)."""
        return [
            DetectedSignal(
                frequency_hz=track.frequency_hz,
                power_db=track.power_db,
                capture_gain_db=track.capture_gain_db,
                detection_count=track.detection_count,
                confirmed_at=track.confirmed_at,
            )
            for track in self._confirmed
        ]

    def confirm_directly(
        self,
        peaks: list[DetectedPeak],
        *,
        capture_gain_db: float = 0.0,
        match_tolerance_hz: float | None = None,
    ) -> None:
        """Promote peaks to confirmed immediately (used by band scanning).

        Existing confirmed entries within the match tolerance are updated in
        place; otherwise a new confirmed row is inserted.
        """
        tolerance_hz = (
            self._match_tolerance_hz
            if match_tolerance_hz is None
            else match_tolerance_hz
        )
        for peak in peaks:
            confirmed = self._find_matching_confirmed(peak.frequency_hz, tolerance_hz)
            if confirmed is not None:
                confirmed.frequency_hz = peak.frequency_hz
                confirmed.power_db = peak.power_db
                confirmed.detection_count += 1
                self._remove_from_list(
                    self._candidates,
                    peak.frequency_hz,
                    tolerance_hz,
                )
                continue

            self._remove_from_list(self._candidates, peak.frequency_hz, tolerance_hz)
            self._promote_candidate(
                _CandidateTrack(
                    frequency_hz=peak.frequency_hz,
                    power_db=peak.power_db,
                    consecutive_hits=self._consecutive_hits_required,
                ),
                capture_gain_db,
            )

    def _promote_candidate(self, candidate: _CandidateTrack, capture_gain_db: float) -> None:
        self._confirmed.insert(
            0,
            _ConfirmedTrack(
                frequency_hz=candidate.frequency_hz,
                power_db=candidate.power_db,
                capture_gain_db=capture_gain_db,
                detection_count=1,
                confirmed_at=self._next_confirmed_at,
            ),
        )
        self._next_confirmed_at += 1

    def _remove_from_list(
        self,
        tracks: list[_CandidateTrack] | list[_ConfirmedTrack],
        frequency_hz: float,
        match_tolerance_hz: float | None = None,
    ) -> bool:
        tolerance_hz = (
            self._match_tolerance_hz
            if match_tolerance_hz is None
            else match_tolerance_hz
        )
        for index, track in enumerate(tracks):
            if abs(track.frequency_hz - frequency_hz) <= tolerance_hz:
                del tracks[index]
                return True
        return False

    def _find_matching_confirmed(
        self,
        frequency_hz: float,
        match_tolerance_hz: float | None = None,
    ) -> _ConfirmedTrack | None:
        tolerance_hz = (
            self._match_tolerance_hz
            if match_tolerance_hz is None
            else match_tolerance_hz
        )
        best_track: _ConfirmedTrack | None = None
        best_distance_hz = float("inf")
        for track in self._confirmed:
            distance_hz = abs(track.frequency_hz - frequency_hz)
            if distance_hz <= tolerance_hz and distance_hz < best_distance_hz:
                best_distance_hz = distance_hz
                best_track = track
        return best_track

    def _find_matching_peak(
        self,
        peaks: list[DetectedPeak],
        matched_peak_indices: set[int],
        reference_freq_hz: float,
    ) -> int | None:
        best_index: int | None = None
        best_distance_hz = float("inf")

        for peak_index, peak in enumerate(peaks):
            if peak_index in matched_peak_indices:
                continue
            distance_hz = abs(peak.frequency_hz - reference_freq_hz)
            if distance_hz <= self._match_tolerance_hz and distance_hz < best_distance_hz:
                best_distance_hz = distance_hz
                best_index = peak_index

        return best_index
