"""
DetectionLoop: thread orchestrator.

Loop:
    1. Ambil frame terbaru dari RTSPReader
    2. Preprocess
    3. Untuk tiap slot aktif: detect_slot() → upsert ke MySQL
    4. Bila status berubah → insert occupancy_log + broadcast WS
    5. Tiap N detik → insert occupancy_summary + broadcast WS summary_tick
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.config import settings
from app.core.detector import DetectionResult, detect_slot
from app.core.preprocessor import preprocess, compute_adaptive_threshold
from app.db.connection import SessionLocal
from app.db import repository as repo
from app.services.rtsp_reader import RTSPReader
from app.services.ws_manager import ws_manager


log = logging.getLogger(__name__)


# Cache polygon di memori; reload tiap N detik.
class _SlotCacheEntry:
    __slots__ = ("id", "code", "polygon")

    def __init__(self, id: int, code: str, polygon: list):
        self.id = id
        self.code = code
        self.polygon = polygon


class DetectionLoop:
    def __init__(self, reader: RTSPReader):
        self.reader = reader
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._slots_cache: List[_SlotCacheEntry] = []
        self._cache_loaded_at: float = 0.0
        self._cache_ttl_sec: float = 5.0

        self._last_summary_at: float = 0.0
        self._latest_overlay: Optional[np.ndarray] = None
        self._overlay_lock = threading.Lock()
        self._fps: float = 0.0
        self._ratio_ema: Dict[int, float] = {}
        self._stable_status: Dict[int, str] = {}
        self._manual_overrides: Dict[int, str] = {}

    # -----------------------------
    # Lifecycle
    # -----------------------------

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="DetectionLoop")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)

    def get_latest_overlay(self) -> Optional[np.ndarray]:
        with self._overlay_lock:
            return None if self._latest_overlay is None else self._latest_overlay.copy()

    def get_fps(self) -> float:
        return self._fps

    # -----------------------------
    # Cache slot
    # -----------------------------

    def _reload_slots_if_needed(self) -> None:
        now = time.time()
        if (now - self._cache_loaded_at) < self._cache_ttl_sec and self._slots_cache:
            return
        with SessionLocal() as session:
            slots = repo.list_slots(session, active_only=True)
            self._slots_cache = [
                _SlotCacheEntry(s.id, s.slot_code, list(s.polygon_json))
                for s in slots
            ]
        self._cache_loaded_at = now

    def force_reload_slots(self) -> None:
        self._cache_loaded_at = 0.0

    def set_manual_override(self, slot_id: int, status: str) -> None:
        self._manual_overrides[slot_id] = status

    def clear_manual_override(self, slot_id: int) -> None:
        self._manual_overrides.pop(slot_id, None)

    def get_manual_overrides(self) -> Dict[int, str]:
        return dict(self._manual_overrides)

    def _smooth_ratio(self, slot_id: int, ratio: float) -> float:
        """Haluskan ratio memakai EMA agar noise frame-to-frame lebih stabil."""
        alpha = min(1.0, max(0.0, settings.ratio_ema_alpha))
        previous = self._ratio_ema.get(slot_id)
        smoothed = ratio if previous is None else (alpha * ratio) + ((1.0 - alpha) * previous)
        self._ratio_ema[slot_id] = smoothed
        return smoothed

    def _apply_hysteresis(self, slot_id: int, ratio: float, threshold: float) -> DetectionResult:
        margin = max(0.0, settings.detection_hysteresis_margin)
        free_threshold = max(0.0, threshold - margin)
        full_threshold = min(1.0, threshold + margin)

        previous = self._stable_status.get(slot_id)
        if previous == "FULL":
            status = "FREE" if ratio <= free_threshold else "FULL"
        elif previous == "FREE":
            status = "FULL" if ratio >= full_threshold else "FREE"
        else:
            status = "FREE" if ratio < threshold else "FULL"

        self._stable_status[slot_id] = status
        return DetectionResult(status=status, ratio=float(ratio))

    # -----------------------------
    # Loop body
    # -----------------------------

    def _run(self) -> None:
        log.info("DetectionLoop start (threshold=%.2f, interval=%dms)",
                 settings.detection_threshold, settings.detect_interval_ms)
        interval = max(0.05, settings.detect_interval_ms / 1000.0)
        ema_dt = 0.0

        while not self._stop.is_set():
            t0 = time.time()
            try:
                self._tick()
            except Exception as e:  # pragma: no cover
                log.exception("DetectionLoop tick error: %s", e)
                time.sleep(1.0)
                continue

            dt = time.time() - t0
            ema_dt = dt if ema_dt == 0 else (ema_dt * 0.8 + dt * 0.2)
            self._fps = 1.0 / ema_dt if ema_dt > 0 else 0.0

            sleep_for = max(0.0, interval - dt)
            self._stop.wait(sleep_for)

        log.info("DetectionLoop stop")

    def _tick(self) -> None:
        frame = self.reader.get_latest_frame()
        if frame is None:
            return

        self._reload_slots_if_needed()
        if not self._slots_cache:
            with self._overlay_lock:
                self._latest_overlay = frame  # tampilkan saja apa adanya
            return

        processed, shadow_mask = preprocess(
            frame,
            threshold_value=settings.preprocess_manual_threshold,
            threshold_mode=settings.preprocess_threshold_mode,
            use_clahe=settings.preprocess_use_clahe,
            adaptive_c=settings.preprocess_adaptive_c,
            remove_shadows=settings.remove_shadows,
            shadow_v_low=settings.shadow_v_low,
            shadow_v_high=settings.shadow_v_high,
            close_ksize=settings.close_ksize,
            dilate_iter=settings.dilate_iterations,
        )

        actual_threshold = settings.detection_threshold
        if settings.adaptive_threshold_enabled:
            actual_threshold = compute_adaptive_threshold(
                frame,
                base_threshold=settings.detection_threshold,
                min_threshold=settings.adaptive_threshold_min,
                max_threshold=settings.adaptive_threshold_max,
            )

        results: Dict[int, DetectionResult] = {}
        for entry in self._slots_cache:
            override = self._manual_overrides.get(entry.id)
            if override is not None:
                results[entry.id] = DetectionResult(status=override, ratio=1.0)
                self._stable_status[entry.id] = override
                continue
            try:
                raw = detect_slot(
                    processed, entry.polygon,
                    threshold=actual_threshold,
                    shadow_mask=shadow_mask,
                    min_object_area=settings.min_object_area,
                )
                smoothed_ratio = self._smooth_ratio(entry.id, raw.ratio)
                results[entry.id] = self._apply_hysteresis(entry.id, smoothed_ratio, actual_threshold)
            except Exception as e:  # pragma: no cover
                log.warning("detect_slot error slot=%s: %s", entry.code, e)

        # Tulis ke DB + broadcast saat berubah.
        free_count = 0
        full_count = 0
        with SessionLocal() as session:
            for entry in self._slots_cache:
                res = results.get(entry.id)
                if res is None:
                    continue
                if res.status == "FREE":
                    free_count += 1
                else:
                    full_count += 1

                changed = repo.upsert_status(session, entry.id, res.status, res.ratio)
                if changed:
                    repo.insert_log(session, entry.id, res.status, res.ratio)
                    ws_manager.broadcast_threadsafe({
                        "type": "slot_changed",
                        "data": {
                            "slot_id": entry.id,
                            "slot_code": entry.code,
                            "status": res.status,
                            "ratio": round(res.ratio, 3),
                            "at": datetime.utcnow().isoformat() + "Z",
                        },
                    })

            # Summary periodik
            now = time.time()
            if (now - self._last_summary_at) >= settings.summary_interval_sec:
                total = len(self._slots_cache)
                repo.insert_summary(
                    session, datetime.utcnow(), total, free_count, full_count
                )
                self._last_summary_at = now
                ws_manager.broadcast_threadsafe({
                    "type": "summary_tick",
                    "data": {
                        "total": total,
                        "free": free_count,
                        "full": full_count,
                        "at": datetime.utcnow().isoformat() + "Z",
                    },
                })

            session.commit()

        # Overlay untuk MJPEG broadcaster (di-handle terpisah).
        overlay = self._draw_overlay(frame, results, free_count, full_count)
        with self._overlay_lock:
            self._latest_overlay = overlay

    # -----------------------------
    # Overlay drawing
    # -----------------------------

    def _draw_overlay(
        self,
        frame: np.ndarray,
        results: Dict[int, DetectionResult],
        free_count: int,
        full_count: int,
    ) -> np.ndarray:
        import cv2

        out = frame.copy()
        for entry in self._slots_cache:
            res = results.get(entry.id)
            color = (0, 255, 0) if (res and res.status == "FREE") else (0, 0, 255)
            pts = np.array(entry.polygon, dtype=np.int32)
            cv2.polylines(out, [pts], True, color, 2)

            # centroid
            M = cv2.moments(pts)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                label = res.status if res else "?"
                cv2.putText(out, label, (cx - 22, cy),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                cv2.putText(out, entry.code, (cx - 18, cy + 16),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        # counter UI
        total = len(self._slots_cache)
        cv2.rectangle(out, (40, 20), (360, 90), (180, 0, 180), -1)
        cv2.putText(out, f"Free: {free_count}/{total}", (55, 65),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        if self._fps > 0:
            cv2.putText(out, f"{self._fps:.1f} FPS", (55, 88),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        return out
