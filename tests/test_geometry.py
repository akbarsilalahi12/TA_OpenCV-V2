"""Unit test untuk app.core.geometry."""

import numpy as np

from app.core.geometry import (
    bounding_rect,
    centroid,
    make_local_mask,
    polygon_area,
    to_np,
)


def test_to_np_shape():
    poly = [[0, 0], [10, 0], [10, 10], [0, 10]]
    pts = to_np(poly)
    assert pts.shape == (4, 2)
    assert pts.dtype == np.int32


def test_bounding_rect_square():
    poly = [[10, 20], [30, 20], [30, 50], [10, 50]]
    x, y, w, h = bounding_rect(poly)
    assert (x, y, w, h) == (10, 20, 21, 31)  # OpenCV bounding rect inclusive


def test_centroid_square():
    poly = [[0, 0], [10, 0], [10, 10], [0, 10]]
    cx, cy = centroid(poly)
    assert abs(cx - 5) <= 1
    assert abs(cy - 5) <= 1


def test_polygon_area_square():
    poly = [[0, 0], [10, 0], [10, 10], [0, 10]]
    assert polygon_area(poly) == 100.0


def test_polygon_area_degenerate():
    poly = [[5, 5], [5, 5], [5, 5]]
    assert polygon_area(poly) == 0.0


def test_make_local_mask():
    poly = [[10, 10], [20, 10], [20, 20], [10, 20]]
    mask, (x, y, w, h) = make_local_mask(poly)
    assert mask.shape == (h, w)
    # Mask harus terisi 255 di tengah area polygon
    assert mask[h // 2, w // 2] == 255
