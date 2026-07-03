"""
Frame broadcaster: generator MJPEG untuk endpoint /video_feed.
Mengambil frame overlay dari DetectionLoop dan encode ke JPEG.
"""

from __future__ import annotations

import time
from typing import Generator

import cv2
import numpy as np

from app.services.detection_loop import DetectionLoop


def _placeholder_frame(w: int = 1280, h: int = 720, msg: str = "Waiting for stream...") -> np.ndarray:
    img = np.zeros((h, w, 3), dtype=np.uint8)
    cv2.putText(img, msg, (40, h // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    return img


def mjpeg_generator(loop: DetectionLoop, fps: int = 15) -> Generator[bytes, None, None]:
    """
    Yield frame JPEG dengan format multipart untuk MJPEG over HTTP.
    """
    boundary = b"--frame"
    interval = 1.0 / max(1, fps)

    while True:
        t0 = time.time()
        frame = loop.get_latest_overlay()
        if frame is None:
            frame = _placeholder_frame()

        ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if not ok:
            continue
        chunk = jpg.tobytes()

        yield (
            boundary
            + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
            + str(len(chunk)).encode()
            + b"\r\n\r\n"
            + chunk
            + b"\r\n"
        )

        dt = time.time() - t0
        if dt < interval:
            time.sleep(interval - dt)
