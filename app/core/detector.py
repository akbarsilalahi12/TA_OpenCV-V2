from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import cv2
import numpy as np

from app.core.geometry import Polygon, make_local_mask, polygon_area


SlotStatus = Literal["FREE", "FULL"]


@dataclass(frozen=True)
class DetectionResult:
    status: SlotStatus
    ratio: float
    shadow_ratio: float = 0.0


def _count_significant_pixels(
    masked: np.ndarray,
    min_object_area: int = 200,
) -> int:
    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(masked, connectivity=8)
    if num_labels <= 1:
        return 0
    return int(sum(
        stats[i, cv2.CC_STAT_AREA]
        for i in range(1, num_labels)
        if stats[i, cv2.CC_STAT_AREA] >= min_object_area
    ))


def detect_slot(
    processed: np.ndarray,
    polygon: Polygon,
    threshold: float = 0.18,
    shadow_mask: Optional[np.ndarray] = None,
    min_object_area: int = 200,
) -> DetectionResult:
    if processed is None or processed.ndim != 2:
        raise ValueError("processed harus gambar biner 2D (H, W)")

    area = polygon_area(polygon)
    if area <= 0:
        return DetectionResult(status="FREE", ratio=0.0)

    mask, (x, y, w, h) = make_local_mask(polygon)

    H, W = processed.shape[:2]

    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + w), min(H, y + h)

    if x1 <= x0 or y1 <= y0:
        return DetectionResult(status="FREE", ratio=0.0)

    roi = processed[y0:y1, x0:x1]

    mx0, my0 = x0 - x, y0 - y
    mx1, my1 = mx0 + (x1 - x0), my0 + (y1 - y0)
    sub_mask = mask[my0:my1, mx0:mx1]

    if roi.shape != sub_mask.shape:
        return DetectionResult(status="FREE", ratio=0.0)

    masked = cv2.bitwise_and(roi, roi, mask=sub_mask)
    count = _count_significant_pixels(masked, min_object_area)

    effective_area = area
    if shadow_mask is not None:
        shadow_roi = shadow_mask[y0:y1, x0:x1]
        if shadow_roi.shape[:2] == sub_mask.shape[:2]:
            shadow_in_poly = cv2.bitwise_and(shadow_roi, shadow_roi, mask=sub_mask)
            shadow_pixels = int(cv2.countNonZero(shadow_in_poly))
            effective_area = max(1.0, area - shadow_pixels)
        else:
            shadow_pixels = 0
    else:
        shadow_pixels = 0

    ratio = count / area
    shadow_ratio = shadow_pixels / area if area > 0 else 0.0
    effective_ratio = count / effective_area if effective_area > 0 else ratio

    status: SlotStatus = "FREE" if effective_ratio < threshold else "FULL"

    return DetectionResult(status=status, ratio=float(ratio), shadow_ratio=float(shadow_ratio))
