"""Stepwise RF band scanning with peak detection."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from sdr_console.detect.peaks import (
    detect_peaks,
    filter_peaks_to_range,
    merge_nearby_peaks,
)
from sdr_console.detect.tracker import SignalTracker
from sdr_console.dsp.averager import SpectrumAverager
from sdr_console.dsp.frame import SpectrumFrame
from sdr_console.pipeline.sample_queue import SampleQueue

if TYPE_CHECKING:
    from sdr_console.hal.interface import SDRDeviceInterface

logger = logging.getLogger(__name__)

DEFAULT_SETTLE_TIME_S = 0.05
DEFAULT_DWELL_FRAMES = 3
DEFAULT_FLUSH_FRAMES = 3
DEFAULT_FRAME_TIMEOUT_S = 2.0


class ScanMode(Enum):
    """How many times the configured band is swept."""

    SINGLE = "single"
    LOOP = "loop"


@dataclass(frozen=True, slots=True)
class ScanProgress:
    """Snapshot of scan state for UI updates."""

    step_index: int
    step_count: int
    center_freq_hz: float
    running: bool = True
    round_index: int = 1
    forward: bool = True


@dataclass(frozen=True, slots=True)
class ScanResult:
    """Outcome after a scan finishes or is stopped."""

    last_detected_freq_hz: float | None
    stopped_early: bool


def min_scan_step_hz(sample_rate_hz: float) -> float:
    """Minimum scan hop size: half the observable bandwidth."""
    if sample_rate_hz <= 0.0:
        raise ValueError("sample_rate_hz must be positive")
    return sample_rate_hz / 2.0


def default_scan_step_hz(sample_rate_hz: float) -> float:
    """Default scan hop size matches the minimum practical step."""
    return min_scan_step_hz(sample_rate_hz)


def compute_scan_centers(
    start_freq_hz: float,
    end_freq_hz: float,
    sample_rate_hz: float,
    step_hz: float,
) -> list[float]:
    """Return receiver center frequencies that cover ``[start_freq_hz, end_freq_hz]``.

    When the requested span fits inside one FFT snapshot, a single center at the
    midpoint is returned and no stepping is required.
    """
    if start_freq_hz > end_freq_hz:
        start_freq_hz, end_freq_hz = end_freq_hz, start_freq_hz
    if sample_rate_hz <= 0.0:
        raise ValueError("sample_rate_hz must be positive")
    if step_hz < min_scan_step_hz(sample_rate_hz):
        raise ValueError(
            f"step_hz must be at least {min_scan_step_hz(sample_rate_hz):g} Hz "
            f"(sample_rate / 2)"
        )

    half_bandwidth_hz = sample_rate_hz / 2.0
    if end_freq_hz - start_freq_hz <= sample_rate_hz:
        return [(start_freq_hz + end_freq_hz) / 2.0]

    centers: list[float] = []
    center_hz = start_freq_hz + half_bandwidth_hz
    while center_hz - half_bandwidth_hz < end_freq_hz - 1e-6:
        centers.append(center_hz)
        center_hz += step_hz

    final_center_hz = end_freq_hz - half_bandwidth_hz
    if not centers or centers[-1] < final_center_hz - 1e-6:
        if final_center_hz >= start_freq_hz + half_bandwidth_hz - 1e-6:
            centers.append(final_center_hz)

    return centers


def centers_for_pass(forward_centers_hz: list[float], *, reverse: bool) -> list[float]:
    """Return center frequencies for one forward or return sweep."""
    if reverse:
        return list(reversed(forward_centers_hz))
    return list(forward_centers_hz)


class ScanController:
    """Tune across a band, average dwell frames, and confirm detected peaks."""

    def __init__(
        self,
        device: SDRDeviceInterface,
        frame_queue: SampleQueue[SpectrumFrame],
        tracker: SignalTracker,
        *,
        fft_size: int,
        start_freq_hz: float,
        end_freq_hz: float,
        step_hz: float,
        threshold_db: float,
        min_distance_hz: float,
        merge_bandwidth_hz: float,
        mode: ScanMode = ScanMode.SINGLE,
        dwell_frames: int = DEFAULT_DWELL_FRAMES,
        flush_frames: int = DEFAULT_FLUSH_FRAMES,
        settle_time_s: float = DEFAULT_SETTLE_TIME_S,
        frame_timeout_s: float = DEFAULT_FRAME_TIMEOUT_S,
        on_progress: Callable[[ScanProgress], None] | None = None,
        on_finished: Callable[[ScanResult], None] | None = None,
        on_step_peaks: Callable[[list], None] | None = None,
    ) -> None:
        del fft_size  # reserved for future synchronous capture paths
        self._device = device
        self._frame_queue = frame_queue
        self._tracker = tracker
        self._start_freq_hz = start_freq_hz
        self._end_freq_hz = end_freq_hz
        self._step_hz = step_hz
        self._threshold_db = threshold_db
        self._min_distance_hz = min_distance_hz
        self._merge_bandwidth_hz = merge_bandwidth_hz
        self._mode = mode
        self._dwell_frames = dwell_frames
        self._flush_frames = flush_frames
        self._settle_time_s = settle_time_s
        self._frame_timeout_s = frame_timeout_s
        self._on_progress = on_progress
        self._on_finished = on_finished
        self._on_step_peaks = on_step_peaks
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_detected_freq_hz: float | None = None
        self._stopped_early = False

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def last_detected_freq_hz(self) -> float | None:
        return self._last_detected_freq_hz

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._stopped_early = False
        self._last_detected_freq_hz = None
        self._thread = threading.Thread(target=self._run, name="ScanController", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> ScanResult | None:
        self._stopped_early = True
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None
        return self._build_result()

    def _build_result(self) -> ScanResult:
        return ScanResult(
            last_detected_freq_hz=self._last_detected_freq_hz,
            stopped_early=self._stopped_early,
        )

    def _emit_finished(self) -> None:
        if self._on_finished is None:
            return
        try:
            self._on_finished(self._build_result())
        except Exception:
            logger.exception("Scan finished callback failed")

    def _emit_progress(
        self,
        step_index: int,
        step_count: int,
        center_freq_hz: float,
        *,
        round_index: int = 1,
        forward: bool = True,
    ) -> None:
        if self._on_progress is None:
            return
        try:
            self._on_progress(
                ScanProgress(
                    step_index=step_index,
                    step_count=step_count,
                    center_freq_hz=center_freq_hz,
                    running=not self._stop_event.is_set(),
                    round_index=round_index,
                    forward=forward,
                )
            )
        except Exception:
            logger.exception("Scan progress callback failed")

    def _run(self) -> None:
        restored_center_hz = self._device.center_freq_hz
        try:
            try:
                forward_centers_hz = compute_scan_centers(
                    self._start_freq_hz,
                    self._end_freq_hz,
                    self._device.sample_rate_hz,
                    self._step_hz,
                )
            except ValueError:
                logger.exception("Invalid scan parameters")
                return

            step_count = len(forward_centers_hz)
            scan_start_hz = min(self._start_freq_hz, self._end_freq_hz)
            scan_end_hz = max(self._start_freq_hz, self._end_freq_hz)
            round_index = 1
            reverse = False

            while not self._stop_event.is_set():
                centers_hz = centers_for_pass(forward_centers_hz, reverse=reverse)
                forward = not reverse

                for step_index, center_freq_hz in enumerate(centers_hz):
                    if self._stop_event.is_set():
                        break

                    self._emit_progress(
                        step_index,
                        step_count,
                        center_freq_hz,
                        round_index=round_index,
                        forward=forward,
                    )
                    try:
                        self._device.set_center_freq(center_freq_hz)
                    except ValueError:
                        logger.exception("Failed to tune to %s Hz", center_freq_hz)
                        self._notify_step_complete([])
                        continue

                    self._frame_queue.drain()
                    if self._settle_time_s > 0.0:
                        time.sleep(self._settle_time_s)
                    self._flush_stale_frames(self._flush_frames)
                    if self._stop_event.is_set():
                        break

                    averaged = self._capture_averaged_frame()
                    if averaged is None:
                        logger.warning(
                            "No spectrum frames captured at %s Hz", center_freq_hz
                        )
                        self._notify_step_complete([])
                        continue

                    step_peaks = detect_peaks(
                        averaged,
                        self._threshold_db,
                        self._min_distance_hz,
                    )
                    step_peaks = merge_nearby_peaks(step_peaks, self._merge_bandwidth_hz)
                    step_peaks = filter_peaks_to_range(
                        step_peaks, scan_start_hz, scan_end_hz
                    )
                    if step_peaks:
                        self._tracker.confirm_directly(
                            step_peaks,
                            capture_gain_db=float(self._device.gain_db),
                            match_tolerance_hz=self._merge_bandwidth_hz,
                        )
                        self._tracker.compact_confirmed(self._merge_bandwidth_hz)
                        self._last_detected_freq_hz = step_peaks[0].frequency_hz

                    self._notify_step_complete(step_peaks)

                if self._mode is ScanMode.SINGLE:
                    break

                reverse = not reverse
                round_index += 1

            self._emit_progress(
                step_count,
                step_count,
                self._device.center_freq_hz,
                round_index=round_index,
                forward=not reverse,
            )
        finally:
            try:
                self._device.set_center_freq(restored_center_hz)
            except ValueError:
                logger.exception("Failed to restore center frequency after scan")
            self._thread = None
            self._emit_finished()

    def _notify_step_complete(self, step_peaks: list) -> None:
        if self._on_step_peaks is None:
            return
        try:
            self._on_step_peaks(step_peaks)
        except Exception:
            logger.exception("Scan step-peaks callback failed")

    def _capture_averaged_frame(self) -> SpectrumFrame | None:
        averager = SpectrumAverager(self._dwell_frames)
        deadline = time.monotonic() + self._frame_timeout_s * self._dwell_frames

        while averager.collected_count < self._dwell_frames:
            if self._stop_event.is_set():
                return None
            if time.monotonic() > deadline:
                break

            frame = self._frame_queue.try_get(timeout=0.1)
            if frame is None:
                continue
            if averager.add(frame):
                break

        return averager.result()

    def _flush_stale_frames(self, count: int) -> None:
        """Drop frames that may still reflect the previous center frequency."""
        if count <= 0:
            return

        flushed = 0
        deadline = time.monotonic() + self._frame_timeout_s * max(count, 1)
        while flushed < count and time.monotonic() < deadline:
            if self._stop_event.is_set():
                return
            frame = self._frame_queue.try_get(timeout=0.1)
            if frame is not None:
                flushed += 1
