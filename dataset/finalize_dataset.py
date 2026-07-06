"""
Finalize PKLot calibration dataset:
  - Parse XML for each matched pair
  - Extract polygon coords + occupancy labels
  - Save polygons.json and per-image JSONs
"""
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

SRC = Path("dataset/pklot_calib")
DST = Path("dataset/pklot")

if DST.exists():
    shutil.rmtree(DST)
DST.mkdir(parents=True)

# Collect per-parking-lot polygons
lot_polygons = {}
all_images = []

for xml_path in sorted(SRC.glob("*.xml")):
    tree = ET.parse(str(xml_path))
    root = tree.getroot()
    lot_id = root.get("id", "unknown")

    polygons = {}
    slots_gt = {}

    for sp in root.findall("space"):
        sid = sp.get("id", "unknown")
        occupied = sp.get("occupied", "0")
        contour = sp.find("contour")
        if contour is None:
            continue
        points = []
        for pt in contour.findall("point"):
            x = float(pt.get("x", 0))
            y = float(pt.get("y", 0))
            points.append([int(x), int(y)])
        if len(points) >= 3:
            polygons[sid] = points
            slots_gt[sid] = "FULL" if occupied == "1" else "FREE"

    # Save per-parking-lot polygons
    if lot_id not in lot_polygons:
        lot_polygons[lot_id] = polygons

    # Copy image
    jpg_path = xml_path.with_suffix(".jpg")
    if jpg_path.exists():
        shutil.copy2(jpg_path, DST / jpg_path.name)

    # Save per-image ground truth (use prefixed slot codes to match polygons.json)
    prefixed_gt = {f"{lot_id}_{k}": v for k, v in slots_gt.items()}
    json_path = DST / f"{xml_path.stem}.json"
    with open(json_path, "w") as f:
        json.dump({"slots": prefixed_gt, "parking_lot": lot_id}, f, indent=2)

    all_images.append(jpg_path.stem)
    print(f"  {jpg_path.stem}: {lot_id}, {len(slots_gt)} slots, "
          f"{sum(1 for v in slots_gt.values() if v == 'FREE')} FREE, "
          f"{sum(1 for v in slots_gt.values() if v == 'FULL')} FULL")

# Save all polygons (flattened: slot code = lot + space id)
all_polygons = {}
for lot_id, polygons in lot_polygons.items():
    for sid, poly in polygons.items():
        all_polygons[f"{lot_id}_{sid}"] = poly

poly_out = DST / "polygons.json"
with open(poly_out, "w") as f:
    json.dump({"polygons": all_polygons}, f, indent=2)

print(f"\n{'='*50}")
print(f"PKLot Calibration Dataset")
print(f"  Images: {len(all_images)}")
print(f"  Parking lots: {list(lot_polygons.keys())}")
print(f"  Total slots defined: {len(all_polygons)}")
print(f"  Location: {DST.resolve()}")
print(f"  Polygons: {poly_out}")
print(f"{'='*50}")
