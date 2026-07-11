"""Unit test untuk app.core.detector."""

import numpy as np
import pytest

from app.core.detector import detect_slot


SQUARE = [[10, 10], [30, 10], [30, 30], [10, 30]]


def test_empty_frame_yields_free():
    img = np.zeros((100, 100), dtype=np.uint8)
    res = detect_slot(img, SQUARE, threshold=0.18)
    assert res.status == "FREE"
    assert res.ratio == 0.0


def test_full_frame_yields_full():
    img = np.full((100, 100), 255, dtype=np.uint8)
    res = detect_slot(img, SQUARE, threshold=0.18)
    assert res.status == "FULL"
    assert res.ratio > 0.9


def test_threshold_boundary():
    img = np.zeros((100, 100), dtype=np.uint8)
    # Isi setengah area polygon dengan 255
    img[10:30, 10:21] = 255  # ~half
    res = detect_slot(img, SQUARE, threshold=0.4)
    assert res.status == "FULL"

    res2 = detect_slot(img, SQUARE, threshold=0.7)
    assert res2.status == "FREE"


def test_polygon_outside_frame_is_free():
    img = np.full((100, 100), 255, dtype=np.uint8)
    out_poly = [[200, 200], [220, 200], [220, 220], [200, 220]]
    res = detect_slot(img, out_poly, threshold=0.18)
    assert res.status == "FREE"
    assert res.ratio == 0.0


def test_degenerate_polygon_is_free():
    img = np.full((100, 100), 255, dtype=np.uint8)
    poly = [[10, 10], [10, 10], [10, 10]]
    res = detect_slot(img, poly, threshold=0.18)
    assert res.status == "FREE"
    assert res.ratio == 0.0


def test_noise_filtered_by_min_object_area():
    img = np.zeros((100, 100), dtype=np.uint8)
    # 10 tiny speckles (5 px each) = 50 white pixels total, but each blob < 200
    for y in range(10):
        img[15 + y * 2, 15:17] = 255
    res = detect_slot(img, SQUARE, threshold=0.18, min_object_area=200)
    assert res.status == "FREE"
    assert res.ratio == 0.0


def test_large_blob_detected_despite_noise():
    img = np.zeros((100, 100), dtype=np.uint8)
    # Real car: big blob of ~1540 px
    img[10:30, 10:24] = 255
    # Noise: tiny specks
    for y in range(20):
        img[35 + y, 35:36] = 255
    res = detect_slot(img, SQUARE, threshold=0.18, min_object_area=200)
    assert res.status == "FULL"
    assert res.ratio > 0.3


def test_invalid_processed_raises():
    bad = np.zeros((10, 10, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        detect_slot(bad, SQUARE)
