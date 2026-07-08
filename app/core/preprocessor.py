from __future__ import annotations

from typing import Optional, Tuple

import cv2
import numpy as np


def _create_shadow_mask(
    frame_bgr: np.ndarray,
    v_low: int = 20,
    v_high: int = 80,
) -> np.ndarray:
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    _, v, _ = cv2.split(hsv)
    shadow = cv2.inRange(v, v_low, v_high)
    kernel = np.ones((5, 5), np.uint8)
    shadow = cv2.morphologyEx(shadow, cv2.MORPH_CLOSE, kernel)
    shadow = cv2.morphologyEx(shadow, cv2.MORPH_OPEN, kernel)
    return shadow


def preprocess(
    frame: np.ndarray,
    blur_ksize: int = 5,
    threshold_value: int = 150,
    threshold_mode: str = "adaptive",
    use_clahe: bool = True,
    adaptive_block_size: int = 25,
    adaptive_c: int = 3,
    median_ksize: int = 5,
    dilate_iter: int = 1,
    remove_shadows: bool = True,
    shadow_v_low: int = 20,
    shadow_v_high: int = 80,
    close_ksize: int = 3,
) -> Tuple[np.ndarray, Optional[np.ndarray]]:
    if frame is None or frame.size == 0:
        raise ValueError("Frame kosong / None")

    if frame.ndim == 2:
        gray = frame
        bgr = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR) if remove_shadows else None
    else:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        bgr = frame if remove_shadows else None

    shadow_mask = None
    if remove_shadows and bgr is not None:
        shadow_mask = _create_shadow_mask(bgr, v_low=shadow_v_low, v_high=shadow_v_high)

    if use_clahe:
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

    blur = cv2.GaussianBlur(gray, (blur_ksize, blur_ksize), 1)

    mode = threshold_mode.lower().strip()
    if mode == "adaptive":
        if adaptive_block_size <= 1:
            adaptive_block_size = 3
        if adaptive_block_size % 2 == 0:
            adaptive_block_size += 1
        thresh = cv2.adaptiveThreshold(
            blur,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            adaptive_block_size,
            adaptive_c,
        )
    elif mode == "otsu":
        _, thresh = cv2.threshold(
            blur,
            0,
            255,
            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
        )
    elif mode == "manual":
        _, thresh = cv2.threshold(
            blur,
            threshold_value,
            255,
            cv2.THRESH_BINARY_INV,
        )
    else:
        raise ValueError("threshold_mode harus salah satu dari: adaptive, otsu, manual")

    if shadow_mask is not None:
        thresh = cv2.bitwise_and(thresh, cv2.bitwise_not(shadow_mask))

    median = cv2.medianBlur(thresh, median_ksize)

    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(median, kernel, iterations=dilate_iter)

    if close_ksize >= 3:
        close_kernel = np.ones((close_ksize, close_ksize), np.uint8)
        dilated = cv2.morphologyEx(dilated, cv2.MORPH_CLOSE, close_kernel)

    return dilated, shadow_mask


def compute_adaptive_threshold(
    frame: np.ndarray,
    base_threshold: float = 0.18,
    min_threshold: float = 0.08,
    max_threshold: float = 0.35,
) -> float:
    if frame is None or frame.size == 0:
        return base_threshold

    if frame.ndim == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame

    mean_brightness = float(np.mean(gray))
    brightness_factor = mean_brightness / 128.0
    adjusted = base_threshold * brightness_factor
    return float(np.clip(adjusted, min_threshold, max_threshold))
