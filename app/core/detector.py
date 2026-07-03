"""
Detector: hitung status FREE/FULL satu polygon slot pada gambar binerisasi.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np

from app.core.geometry import Polygon, make_local_mask, polygon_area


SlotStatus = Literal["FREE", "FULL"]


@dataclass(frozen=True)
class DetectionResult:
    status: SlotStatus
    ratio: float  # 0.0 - 1.0


def detect_slot(
    processed: np.ndarray,
    polygon: Polygon,
    threshold: float = 0.18,
) -> DetectionResult:
    """
    Hitung status satu slot.

    Args:
        processed: gambar biner uint8 (output preprocessor) shape (H, W).
        polygon: list titik [[x,y], ...] dalam koordinat frame.
        threshold: ratio cutoff. ratio < threshold => FREE.

    Returns:
        DetectionResult(status, ratio).

    Catatan:
        - Bila area polygon 0 -> dianggap FREE dengan ratio 0.0.
        - Polygon yang seluruhnya di luar frame -> ratio 0.0 (FREE).
    """
    if processed is None or processed.ndim != 2:
        raise ValueError("processed harus gambar biner 2D (H, W)")

    area = polygon_area(polygon)
    if area <= 0:
        return DetectionResult(status="FREE", ratio=0.0)

    mask, (x, y, w, h) = make_local_mask(polygon)

    H, W = processed.shape[:2]

    # Clamp ROI ke dalam frame.
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + w), min(H, y + h)

    if x1 <= x0 or y1 <= y0:
        return DetectionResult(status="FREE", ratio=0.0)

    roi = processed[y0:y1, x0:x1]

    # Sesuaikan mask dengan area clamp.
    mx0, my0 = x0 - x, y0 - y
    mx1, my1 = mx0 + (x1 - x0), my0 + (y1 - y0)
    sub_mask = mask[my0:my1, mx0:mx1]

    if roi.shape != sub_mask.shape:
        # Safety: kalau ada mismatch, anggap FREE.
        return DetectionResult(status="FREE", ratio=0.0)

    masked = cv2.bitwise_and(roi, roi, mask=sub_mask)
    count = int(cv2.countNonZero(masked))

    ratio = count / area
    status: SlotStatus = "FREE" if ratio < threshold else "FULL"

    return DetectionResult(status=status, ratio=float(ratio))
