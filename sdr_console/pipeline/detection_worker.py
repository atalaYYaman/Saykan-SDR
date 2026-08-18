"""Worker thread that runs peak detection parallel to visualization."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from sdr_console.detect.detected_signal import DetectedSignal
from sdr_console.detect.identified import IdentifiedPeak
from sdr_console.detect.peaks import (
    DEFAULT_MERGE_BANDWIDTH_HZ,
    detect_peaks,
    merge_nearby_peaks,
)
from sdr_console.detect.station_db import (
    DEFAULT_STATION_MATCH_TOLERANCE_HZ,
    StationDatabase,
)
from sdr_console.detect.tracker import SignalTracker
from sdr_console.dsp.frame import SpectrumFrame
from sdr_console.pipeline.detection_state import DetectionState
from sdr_console.pipeline.sample_queue import SampleQueue

if TYPE_CHECKING:
    from sdr_console.hal.interface import SDRDeviceInterface

logger = logging.getLogger(__name__)


class DetectionWorker:
    """Consumes ``SpectrumFrame`` rows and maintains confirmed detections.

    The worker thread stays alive while attached to the pipeline, but heavy
    work is skipped while :meth:`set_enabled` is ``False`` so detection can be
    toggled without restarting threads.
    """

    def __init__(
        self,
        input_queue: SampleQueue[SpectrumFrame],
        state: DetectionState | None = None,
        *,
        threshold_db: float = -40.0,
        min_distance_hz: float = 50_000.0,
        merge_bandwidth_hz: float = DEFAULT_MERGE_BANDWIDTH_HZ,
        window_frames: int = 5,
        confirm_hits: int = 3,
        match_tolerance_hz: float | None = None,
        stale_timeout_s: float = 3.0,
        station_db: StationDatabase | None = None,
        station_match_tolerance_hz: float = DEFAULT_STATION_MATCH_TOLERANCE_HZ,
        device: SDRDeviceInterface | None = None,
        poll_timeout_s: float = 0.1,
    ) -> None:
        del match_tolerance_hz, window_frames, stale_timeout_s
        self._input_queue = input_queue
        self._state = state or DetectionState()
        self._device = device
        consecutive_hits_required = confirm_hits if confirm_hits >= 1 else 3
        self._tracker = SignalTracker(
            consecutive_hits_required=consecutive_hits_required,
            match_tolerance_hz=merge_bandwidth_hz,
        )
        self._station_db = station_db
        self._station_match_tolerance_hz = station_match_tolerance_hz
        self._poll_timeout_s = poll_timeout_s
        self._enabled_event = threading.Event()
        self._stop_event = threading.Event()
        self._settings_lock = threading.Lock()
        self._threshold_db = threshold_db
        self._min_distance_hz = min_distance_hz
        self._merge_bandwidth_hz = merge_bandwidth_hz
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def state(self) -> DetectionState:
        return self._state

    @property
    def enabled(self) -> bool:
        return self._enabled_event.is_set()

    def set_enabled(self, enabled: bool) -> None:
        if enabled:
            self._enabled_event.set()
            return

        self._enabled_event.clear()
        self.reset()
        self._input_queue.drain()

    def set_threshold_db(self, threshold_db: float) -> None:
        with self._settings_lock:
            self._threshold_db = threshold_db

    def set_min_distance_hz(self, min_distance_hz: float) -> None:
        if min_distance_hz < 0.0:
            raise ValueError("min_distance_hz must be non-negative")
        with self._settings_lock:
            self._min_distance_hz = min_distance_hz

    def set_merge_bandwidth_hz(self, merge_bandwidth_hz: float) -> None:
        if merge_bandwidth_hz <= 0.0:
            raise ValueError("merge_bandwidth_hz must be positive")
        with self._settings_lock:
            self._merge_bandwidth_hz = merge_bandwidth_hz
            self._tracker.set_match_tolerance_hz(merge_bandwidth_hz)
            self._tracker.compact_confirmed(merge_bandwidth_hz)
        self._publish_confirmed_peaks()

    def set_station_db(self, station_db: StationDatabase | None) -> None:
        with self._settings_lock:
            self._station_db = station_db

    def reload_station_db(self, path: Path | None = None) -> None:
        """Reload the station database from disk and refresh published state."""
        with self._settings_lock:
            self._station_db = StationDatabase.load(path)
        self._publish_confirmed_peaks()

    def refresh_published_state(self) -> None:
        """Re-publish confirmed peaks to :attr:`state` (e.g. after external tracker updates)."""
        self._publish_confirmed_peaks()

    def reset(self) -> None:
        """Clear candidate tracks and published state."""
        self._tracker.reset_candidates()
        self._state.clear()

    def reset_candidates(self) -> None:
        """Drop only in-progress candidate tracks."""
        self._tracker.reset_candidates()

    def clear_all(self) -> None:
        """Remove every confirmed and candidate track."""
        self._tracker.clear_all()
        self._state.clear()

    def remove(self, frequency_hz: float) -> bool:
        """Remove one confirmed or candidate track near ``frequency_hz``."""
        removed = self._tracker.remove(frequency_hz)
        if removed:
            self._publish_confirmed_peaks()
        return removed

    def remove_many(self, frequencies_hz: list[float]) -> int:
        """Remove multiple tracks and publish once."""
        removed_count = 0
        for frequency_hz in frequencies_hz:
            if self._tracker.remove(frequency_hz):
                removed_count += 1
        if removed_count:
            self._publish_confirmed_peaks()
        return removed_count

    @property
    def tracker(self) -> SignalTracker:
        return self._tracker

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="DetectionWorker",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def _run(self) -> None:
        while not self._stop_event.is_set():
            frame = self._input_queue.try_get(timeout=self._poll_timeout_s)
            if frame is None:
                continue
            if not self._enabled_event.is_set():
                self._input_queue.drain()
                continue

            with self._settings_lock:
                threshold_db = self._threshold_db
                min_distance_hz = self._min_distance_hz
                merge_bandwidth_hz = self._merge_bandwidth_hz

            try:
                peaks = detect_peaks(frame, threshold_db, min_distance_hz)
                peaks = merge_nearby_peaks(peaks, merge_bandwidth_hz)
                self._tracker.update(
                    peaks,
                    frame.timestamp,
                    capture_gain_db=self._current_capture_gain_db(),
                )
                self._publish_confirmed_peaks()
            except Exception:
                logger.exception("Signal detection failed; continuing")

    def _current_capture_gain_db(self) -> float:
        if self._device is None:
            return 0.0
        return float(self._device.gain_db)

    def _publish_confirmed_peaks(self) -> None:
        with self._settings_lock:
            merge_bandwidth_hz = self._merge_bandwidth_hz
        self._tracker.compact_confirmed(merge_bandwidth_hz)
        confirmed = self._tracker.confirmed_signals()
        if self._station_db is None or not self._station_db.entries:
            self._state.replace([self._to_identified_peak(signal) for signal in confirmed])
            return

        identified: list[IdentifiedPeak] = []
        for signal in confirmed:
            name = self._station_db.lookup(
                signal.frequency_hz,
                self._station_match_tolerance_hz,
            )
            identified.append(self._to_identified_peak(signal, name=name))
        self._state.replace(identified)

    def _to_identified_peak(
        self,
        signal: DetectedSignal,
        *,
        name: str | None = None,
    ) -> IdentifiedPeak:
        return IdentifiedPeak.from_signal(signal, name=name)
