"""
Preprocessor: konversi frame BGR menjadi gambar biner siap-deteksi.

Pipeline default:
    grayscale -> CLAHE -> Gaussian blur -> adaptive threshold inversi -> median blur -> dilasi
"""

from __future__ import annotations

import cv2
import numpy as np


def preprocess(
    frame: np.ndarray,
    blur_ksize: int = 5,
    threshold_value: int = 150,
    threshold_mode: str = "adaptive",
    use_clahe: bool = True,
    adaptive_block_size: int = 25,
    adaptive_c: int = 5,
    median_ksize: int = 5,
    dilate_iter: int = 1,
) -> np.ndarray:
    """
    Ubah frame BGR menjadi gambar biner (uint8) untuk deteksi rasio piksel.

    Args:
        frame: input BGR (H, W, 3).
        blur_ksize: kernel Gaussian blur (ganjil).
        threshold_value: nilai cutoff untuk mode manual.
        threshold_mode: mode threshold: "adaptive", "otsu", atau "manual".
        use_clahe: aktifkan normalisasi kontras lokal agar tahan perubahan cahaya.
        adaptive_block_size: ukuran blok adaptive threshold (ganjil dan > 1).
        adaptive_c: konstanta pengurang pada adaptive threshold.
        median_ksize: kernel median blur (ganjil).
        dilate_iter: jumlah iterasi dilasi.

    Returns:
        np.ndarray uint8 (H, W) bernilai 0 atau 255.
    """
    if frame is None or frame.size == 0:
        raise ValueError("Frame kosong / None")

    if frame.ndim == 2:
        gray = frame
    else:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    if use_clahe:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

    blur = cv2.GaussianBlur(gray, (blur_ksize, blur_ksize), 1)

    mode = threshold_mode.lower().strip()
    if mode == "adaptive":
        # block size harus ganjil dan > 1 untuk adaptiveThreshold.
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

    median = cv2.medianBlur(thresh, median_ksize)

    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(median, kernel, iterations=dilate_iter)

    return dilated
