"""
Helper geometri polygon. Tidak ada I/O.
"""

from __future__ import annotations

from typing import Sequence, Tuple

import cv2
import numpy as np


Polygon = Sequence[Sequence[int]]  # [[x,y], [x,y], ...]


def to_np(polygon: Polygon) -> np.ndarray:
    """Konversi list polygon ke np.int32 (N, 2)."""
    return np.array(polygon, dtype=np.int32)


def bounding_rect(polygon: Polygon) -> Tuple[int, int, int, int]:
    """Return (x, y, w, h) bounding box polygon."""
    pts = to_np(polygon)
    x, y, w, h = cv2.boundingRect(pts)
    return int(x), int(y), int(w), int(h)


def centroid(polygon: Polygon) -> Tuple[int, int]:
    """
    Hitung centroid polygon menggunakan moments.
    Fallback ke rata-rata titik bila area = 0.
    """
    pts = to_np(polygon)
    M = cv2.moments(pts)

    if M["m00"] != 0:
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
    else:
        cx = int(np.mean(pts[:, 0]))
        cy = int(np.mean(pts[:, 1]))

    return cx, cy


def polygon_area(polygon: Polygon) -> float:
    """Luas polygon dalam piksel kuadrat."""
    pts = to_np(polygon)
    return float(cv2.contourArea(pts))


def make_local_mask(polygon: Polygon) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
    """
    Bangun mask lokal (sesuai bounding box polygon).

    Returns:
        (mask_uint8 (h, w), (x, y, w, h))
    """
    x, y, w, h = bounding_rect(polygon)
    pts = to_np(polygon)
    local_pts = pts - np.array([x, y], dtype=np.int32)
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask, [local_pts], 255)
    return mask, (x, y, w, h)
