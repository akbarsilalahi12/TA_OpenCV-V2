"""
Kalibrasi threshold deteksi berbasis dataset.

Dataset structure:
    dataset/
        day/
            frame_001.jpg
            frame_001.json       # ground truth: {"slots": {"S001": "FREE", "S002": "FULL", ...}}
            frame_002.jpg
            frame_002.json
            ...
        night/
            frame_010.jpg
            frame_010.json
            ...

Usage:
    python -m app.tools.calibrate_threshold --dataset ./dataset --polygons ./polygons.json

Output:
    - Mencetak threshold optimal + akurasi per kondisi pencahayaan.
    - (opsional) Menulis rekomendasi ke .env
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from app.core.detector import DetectionResult, detect_slot
from app.core.preprocessor import preprocess, compute_adaptive_threshold
from app.core.geometry import Polygon


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("calibrate")


def load_dataset(dataset_path: str) -> List[Tuple[str, np.ndarray, Dict[str, str]]]:
    images = []
    path = Path(dataset_path)
    if not path.is_dir():
        log.error("Dataset path not found: %s", dataset_path)
        return images

    for f in sorted(path.iterdir()):
        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp"):
            json_file = f.with_suffix(".json")
            if not json_file.exists():
                continue
            with open(json_file) as jf:
                ground_truth = json.load(jf)
            img = cv2.imread(str(f))
            if img is None:
                log.warning("Cannot read image: %s", f)
                continue
            slots_data = ground_truth.get("slots", {})
            images.append((f.stem, img, slots_data))
    return images


def evaluate_threshold(
    images: List[Tuple[str, np.ndarray, Dict[str, str]]],
    polygons: Dict[str, Polygon],
    threshold: float,
    threshold_mode: str = "adaptive",
    use_clahe: bool = True,
    remove_shadows: bool = True,
    adaptive_enabled: bool = False,
) -> Tuple[float, int, int, Dict[str, List[str]]]:
    correct = 0
    total = 0
    errors: Dict[str, List[str]] = {}

    for name, frame, gt in images:
        processed, shadow_mask = preprocess(
            frame,
            threshold_mode=threshold_mode,
            use_clahe=use_clahe,
            remove_shadows=remove_shadows,
        )

        actual_threshold = threshold
        if adaptive_enabled:
            actual_threshold = compute_adaptive_threshold(frame, base_threshold=threshold)

        for slot_code, expected_status in gt.items():
            poly = polygons.get(slot_code)
            if poly is None:
                continue
            try:
                result = detect_slot(
                    processed, poly,
                    threshold=actual_threshold,
                    shadow_mask=shadow_mask,
                )
            except Exception:
                continue

            total += 1
            if result.status == expected_status:
                correct += 1
            else:
                key = f"{name}/{slot_code}"
                errors.setdefault(name, []).append(
                    f"{slot_code}: expected={expected_status}, got={result.status}, "
                    f"ratio={result.ratio:.3f}, shadow={result.shadow_ratio:.3f}"
                )

    accuracy = correct / total if total > 0 else 0.0
    return accuracy, correct, total, errors


def load_polygons(polygons_path: str) -> Dict[str, Polygon]:
    with open(polygons_path) as f:
        data = json.load(f)
    if isinstance(data, list):
        return {item["slot_code"]: item["polygon"] for item in data}
    return data.get("polygons", data)


def scan_thresholds(
    images: List[Tuple[str, np.ndarray, Dict[str, str]]],
    polygons: Dict[str, Polygon],
    threshold_mode: str = "adaptive",
    use_clahe: bool = True,
    remove_shadows: bool = True,
    adaptive_enabled: bool = False,
) -> None:
    best_acc = 0.0
    best_th = 0.18
    results = []

    for th in [x / 100 for x in range(5, 51, 1)]:
        acc, correct, total, errors = evaluate_threshold(
            images, polygons, th,
            threshold_mode=threshold_mode,
            use_clahe=use_clahe,
            remove_shadows=remove_shadows,
            adaptive_enabled=adaptive_enabled,
        )
        results.append((th, acc, correct, total))
        log.info("  threshold=%.2f → accuracy=%.2f%% (%d/%d)", th, acc * 100, correct, total)

        if acc > best_acc:
            best_acc = acc
            best_th = th

    return best_th, best_acc, results


def main() -> None:
    parser = argparse.ArgumentParser(description="Kalibrasi threshold deteksi parkir")
    parser.add_argument("--dataset", required=True, help="Path ke folder dataset")
    parser.add_argument("--polygons", required=True, help="Path ke file JSON polygons")
    parser.add_argument("--mode", default="adaptive", choices=["adaptive", "otsu", "manual"])
    parser.add_argument("--no-clahe", action="store_false", dest="use_clahe")
    parser.add_argument("--no-shadow-removal", action="store_false", dest="remove_shadows")
    parser.add_argument("--enable-adaptive-threshold", action="store_true",
                        dest="adaptive_enabled")
    parser.add_argument("--day-only", action="store_true", dest="day_only")
    parser.add_argument("--night-only", action="store_true", dest="night_only")
    args = parser.parse_args()

    polygons = load_polygons(args.polygons)
    log.info("Loaded %d polygons", len(polygons))

    all_images = load_dataset(args.dataset)
    if not all_images:
        log.error("No labeled images found in %s", args.dataset)
        sys.exit(1)

    if args.day_only:
        images = [(n, f, g) for n, f, g in all_images if n.startswith("day")]
    elif args.night_only:
        images = [(n, f, g) for n, f, g in all_images if n.startswith("night")]
    else:
        images = all_images

    log.info("Evaluating %d labeled images...", len(images))

    # Full scan
    print("\n=== Full Threshold Scan ===")
    best_th, best_acc, _ = scan_thresholds(
        images, polygons,
        threshold_mode=args.mode,
        use_clahe=args.use_clahe,
        remove_shadows=args.remove_shadows,
        adaptive_enabled=args.adaptive_enabled,
    )

    print(f"\n{'='*50}")
    print(f"Best threshold: {best_th:.2f} (accuracy: {best_acc*100:.1f}%)")
    print(f"Dataset: {len(images)} images, {len(polygons)} slots")

    if args.adaptive_enabled and not args.day_only and not args.night_only:
        combined = all_images
        day_imgs = [(n, f, g) for n, f, g in combined if n.startswith("day")]
        night_imgs = [(n, f, g) for n, f, g in combined if n.startswith("night")]

        if day_imgs and night_imgs:
            print(f"\n--- Day subset ({len(day_imgs)} images) ---")
            day_th, day_acc, _ = scan_thresholds(
                day_imgs, polygons,
                threshold_mode=args.mode,
                use_clahe=args.use_clahe,
                remove_shadows=args.remove_shadows,
                adaptive_enabled=False,
            )
            print(f"Day best: threshold={day_th:.2f}, accuracy={day_acc*100:.1f}%")

            print(f"\n--- Night subset ({len(night_imgs)} images) ---")
            night_th, night_acc, _ = scan_thresholds(
                night_imgs, polygons,
                threshold_mode=args.mode,
                use_clahe=args.use_clahe,
                remove_shadows=args.remove_shadows,
                adaptive_enabled=False,
            )
            print(f"Night best: threshold={night_th:.2f}, accuracy={night_acc*100:.1f}%")

    print(f"\nRecommendation:")
    print(f"  Set DETECTION_THRESHOLD={best_th:.2f} in .env")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
