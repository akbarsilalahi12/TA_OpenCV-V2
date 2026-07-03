"""
RTSPReader: thread yang membaca stream RTSP terus-menerus dan menyimpan
frame terbaru di buffer. Auto-reconnect bila stream putus.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional, Tuple

import cv2
import numpy as np


log = logging.getLogger(__name__)


class RTSPReader:
    def __init__(
        self,
        url: str,
        target_size: Optional[Tuple[int, int]] = (1280, 720),
        reconnect_delay_sec: float = 2.0,
    ):
        self.url = url
        self.target_size = target_size
        self.reconnect_delay = reconnect_delay_sec

        self._cap: Optional[cv2.VideoCapture] = None
        self._frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._connected = False
        self._on_reconnect = None  # callable(message: str)

    # -----------------------------
    # Lifecycle
    # -----------------------------

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="RTSPReader")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def get_latest_frame(self) -> Optional[np.ndarray]:
        with self._frame_lock:
            return None if self._frame is None else self._frame.copy()

    def set_event_callback(self, cb) -> None:
        """Daftarkan callback dipanggil dengan (event_type, message) untuk audit."""
        self._on_reconnect = cb

    # -----------------------------
    # Internal
    # -----------------------------

    def _open(self) -> Optional[cv2.VideoCapture]:
        cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
        if not cap.isOpened():
            cap.release()
            return None
        return cap

    def _emit(self, event_type: str, message: str) -> None:
        cb = self._on_reconnect
        if cb is None:
            return
        try:
            cb(event_type, message)
        except Exception as e:  # pragma: no cover
            log.warning("RTSP event callback error: %s", e)

    def _run(self) -> None:
        log.info("RTSPReader start")
        while not self._stop.is_set():
            if self._cap is None or not self._cap.isOpened():
                log.info("RTSP connecting...")
                self._cap = self._open()
                if self._cap is None:
                    self._connected = False
                    self._emit("RTSP_DISCONNECT", "Gagal connect, retry...")
                    time.sleep(self.reconnect_delay)
                    continue
                self._connected = True
                self._emit("RTSP_RECONNECT", "Connected")

            # buang frame lama
            self._cap.grab()
            ret, frame = self._cap.read()
            if not ret or frame is None:
                log.warning("Frame lost, akan reconnect")
                self._cap.release()
                self._cap = None
                self._connected = False
                self._emit("RTSP_DISCONNECT", "Frame lost")
                time.sleep(self.reconnect_delay)
                continue

            if self.target_size is not None:
                frame = cv2.resize(frame, self.target_size)

            with self._frame_lock:
                self._frame = frame

        log.info("RTSPReader stop")
