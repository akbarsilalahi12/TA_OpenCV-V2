"""Unit test untuk app.core.preprocessor."""

import numpy as np
import pytest

from app.core.preprocessor import preprocess


def _extract(out):
    """preprocess returns (binary, shadow_mask); extract binary for tests."""
    return out[0] if isinstance(out, tuple) else out


def test_preprocess_shape_bgr():
    frame = np.full((100, 100, 3), 200, dtype=np.uint8)
    out = _extract(preprocess(frame))
    assert out.shape == (100, 100)
    assert out.dtype == np.uint8


def test_preprocess_shape_gray():
    frame = np.full((50, 50), 200, dtype=np.uint8)
    out = _extract(preprocess(frame))
    assert out.shape == (50, 50)


def test_preprocess_white_yields_zeros():
    frame = np.full((30, 30, 3), 250, dtype=np.uint8)
    out = _extract(preprocess(frame, threshold_mode="manual", use_clahe=False, remove_shadows=False))
    assert int(out.sum()) == 0


def test_preprocess_dark_yields_white():
    frame = np.full((30, 30, 3), 50, dtype=np.uint8)
    out = _extract(preprocess(frame, threshold_mode="manual", use_clahe=False, remove_shadows=False))
    assert (out > 0).all()


def test_preprocess_adaptive_outputs_binary_image():
    frame = np.tile(np.arange(60, dtype=np.uint8), (60, 1))
    out = _extract(preprocess(frame, threshold_mode="adaptive", use_clahe=True))
    assert out.shape == (60, 60)
    assert out.dtype == np.uint8
    assert set(np.unique(out)).issubset({0, 255})


def test_preprocess_invalid_threshold_mode_raises():
    frame = np.full((30, 30, 3), 100, dtype=np.uint8)
    with pytest.raises(ValueError):
        preprocess(frame, threshold_mode="unknown")


def test_preprocess_empty_raises():
    with pytest.raises(ValueError):
        preprocess(None)
