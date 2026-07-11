# YOLO Object Detection — Ganti Pixel Counting

## Problem
Pixel counting raw: bayangan, tekstur aspal, noise cahaya bikin false positive. Satu slot kosong terdeteksi FULL karena tekstur aspal menghasilkan pixel putih.

## Solusi: YOLOv8n Object Detection
Ganti hitung pixel putih dengan **YOLO** yang detect mobil/motor/bus/truk beneran. Lalu centroid kendaraan di dalam polygon slot = FULL. Tidak bakal false positive karena tekstur aspal — YOLO cuma detect kendaraan.

### Overlap logic: Centroid check
`cv2.pointPolygonTest(polygon, (cx, cy), False) >= 0` → vehicle centroid di dalam polygon → FULL.

### YOLO smoothing: Frame-based state machine
Ratio-based hysteresis (`_smooth_ratio` + `_apply_hysteresis`) gak cocok — YOLO output per-frame binary (detected/not). Ganti pakai **consecutive frame counter**:
- `hits >= CONFIRM` (3 frame berturut-turut ada kendaraan) → **FULL**
- `misses >= CLEAR` (5 frame berturut-turut tidak ada) → **FREE**
- Belum mencapai batas → pertahankan status sebelumnya (anti-flicker)

## Design Decisions

| Decision | Choice |
|---|---|
| Model | YOLOv8n (nano — cepat di CPU) |
| Overlap | Centroid check — simple, reliable |
| Smoothing | Frame-based state machine (eliminates per-slot threshold need) |
| Vehicle classes | car(2), motorcycle(3), bus(5), truck(7) — COCO |
| Fallback mode | Keep pixel counting as `--legacy` config flag |
| Preprocessing | Skip entirely in YOLO mode — just need raw frame |

## Files Changed

### 1. `requirements.txt` — tambah dependency
```
ultralytics>=8.0.0
```

### 2. `app/config.py` — tambah object detection settings
```python
# === Object Detection (YOLO) ===
use_object_detection: bool = True
yolo_model_path: str = "yolov8n.pt"
yolo_confidence: float = 0.4
yolo_device: str = "cpu"                     # "cpu", "cuda"
yolo_confirm_frames: int = 3                 # consecutive hits → FULL
yolo_clear_frames: int = 5                   # consecutive misses → FREE
yolo_vehicle_classes: list[int] = [2, 3, 5, 7]  # car, mc, bus, truck
```

### 3. `app/core/object_detector.py` — NEW file
Class `VehicleDetector`:
```python
from ultralytics import YOLO
import cv2
import numpy as np
from dataclasses import dataclass

COCO_VEHICLES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

@dataclass
class Detection:
    bbox: tuple      # (x1, y1, x2, y2)
    confidence: float
    class_id: int
    class_name: str
    centroid: tuple  # (cx, cy)

class VehicleDetector:
    def __init__(self, model_path="yolov8n.pt", confidence=0.4, device="cpu", vehicle_classes=None):
        self.model = YOLO(model_path)
        self.confidence = confidence
        self.device = device
        self.vehicle_classes = vehicle_classes or list(COCO_VEHICLES.keys())

    def detect(self, frame: np.ndarray) -> list[Detection]:
        results = self.model(frame, conf=self.confidence, device=self.device, verbose=False)
        detections = []
        if not results:
            return detections
        for box in results[0].boxes:
            cls_id = int(box.cls[0])
            if cls_id not in self.vehicle_classes:
                continue
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            detections.append(Detection(
                bbox=(x1, y1, x2, y2),
                confidence=float(box.conf[0]),
                class_id=cls_id,
                class_name=COCO_VEHICLES.get(cls_id, "vehicle"),
                centroid=(cx, cy),
            ))
        return detections

def check_vehicle_in_polygon(polygon, detections) -> bool:
    """True jika centroid kendaraan ada di dalam polygon."""
    pts = np.array(polygon, dtype=np.int32)
    for d in detections:
        if cv2.pointPolygonTest(pts, d.centroid, False) >= 0:
            return True
    return False
```

### 4. `app/core/detector.py` — tambah fungsi YOLO helper
```python
def detect_slot_yolo(polygon, detections, confirm_frames=3, clear_frames=5,
                     consecutive_hits: dict = None, consecutive_misses: dict = None,
                     slot_id: int = 0, stable_status: dict = None) -> DetectionResult:
    """YOLO-based detection with frame-based state machine."""
    if consecutive_hits is None:
        consecutive_hits = {}
    if consecutive_misses is None:
        consecutive_misses = {}

    detected = check_vehicle_in_polygon(polygon, detections)

    if detected:
        consecutive_hits[slot_id] = consecutive_hits.get(slot_id, 0) + 1
        consecutive_misses[slot_id] = 0
    else:
        consecutive_misses[slot_id] = consecutive_misses.get(slot_id, 0) + 1
        consecutive_hits[slot_id] = 0

    previous = (stable_status or {}).get(slot_id)
    if previous == "FULL":
        status = "FREE" if consecutive_misses.get(slot_id, 0) >= clear_frames else "FULL"
    elif previous == "FREE":
        status = "FULL" if consecutive_hits.get(slot_id, 0) >= confirm_frames else "FREE"
    else:
        status = "FREE" if not detected else "FULL"

    ratio = 1.0 if detected else 0.0
    return DetectionResult(status=status, ratio=ratio)
```

### 5. `app/services/detection_loop.py` — UPDATE signifikan
**5a.** Init `VehicleDetector` di `__init__`:
```python
self._vehicle_detector: Optional[VehicleDetector] = None
if settings.use_object_detection:
    try:
        self._vehicle_detector = VehicleDetector(
            model_path=settings.yolo_model_path,
            confidence=settings.yolo_confidence,
            device=settings.yolo_device,
        )
        log.info("YOLO initialized: %s", settings.yolo_model_path)
    except Exception as e:
        log.error("YOLO init failed, fallback to pixel counting: %s", e)
```

**5b.** Di `_tick()`, cabang deteksi utama:
```python
if self._vehicle_detector is not None:
    # YOLO mode — skip preprocessing entirely
    detections = self._vehicle_detector.detect(frame)
    for entry in self._slots_cache:
        override = self._manual_overrides.get(entry.id)
        if override is not None:
            results[entry.id] = DetectionResult(status=override, ratio=1.0)
            continue
        results[entry.id] = detect_slot_yolo(
            entry.polygon, detections,
            confirm_frames=settings.yolo_confirm_frames,
            clear_frames=settings.yolo_clear_frames,
            consecutive_hits=self._yolo_hits,
            consecutive_misses=self._yolo_misses,
            slot_id=entry.id,
            stable_status=self._stable_status,
        )
    # overlay with YOLO bboxes
    overlay = self._draw_yolo_overlay(frame, results, detections, free_count, full_count)
else:
    # existing pixel counting logic (unchanged)
    ...
```

**5c.** Tambah state baru:
```python
self._yolo_hits: Dict[int, int] = {}
self._yolo_misses: Dict[int, int] = {}
```

**5d.** New overlay method `_draw_yolo_overlay()` — sama seperti `_draw_overlay` tapi tambah YOLO bounding boxes + labels.

**5e.** Skip preprocessing entirely in YOLO mode (line 184-203 can be skipped).

### 6. `app/services/detection_loop.py` — frame-based state machine state
```python
# Existing states, plus:
self._yolo_hits: Dict[int, int] = {}      # consecutive detections per slot
self._yolo_misses: Dict[int, int] = {}    # consecutive misses per slot
```

Reset these when slot list reloads.

### 7. `app/core/preprocessor.py` — tidak diubah (masih dipakai buat fallback pixel counting)

### 8. `run_engine.py` — tidak diubah

## Model Download
YOLOv8n otomatis download saat pertama kali `YOLO("yolov8n.pt")` dipanggil:
```powershell
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
```
Download ~6MB, simpan di cache system.

## Edge Cases
- **YOLO miss frame** (kendaraan terdeteksi tapi 1 frame kelewatan) → state machine pakai `clear_frames=5` → butuh 5 miss berturut-turut sebelum FREE. Flicker aman.
- **Kendaraan baru parkir** → butuh `confirm_frames=3` frame berturut-turut → ~0.6-1 detik delay baru jadi FULL. Acceptable.
- **YOLO model fail load** → fallback otomatis ke pixel counting (existing logic). Graceful degradation.
- **Motor kecil di slot besar** → centroid masuk polygon → tetap terdeteksi. OK.
- **Mobil di 2 slot (parkir miring)** → centroid hanya di 1 polygon, slot lain tetap FREE. Akurat.

## Dependencies
- `ultralytics>=8.0.0` (includes torch, torchvision)
- ~500MB install size (YOLOv8n model ~6MB)
- No GPU needed — runs on CPU ~10-20 FPS depending on hardware

## Risiko & Mitigasi
| Risiko | Mitigasi |
|---|---|
| CPU overload (YOLO slow) | Only run inference every N frames (`detect_interval_ms` still applies) |
| Model download gagal | Manual download instructions in docs |
| False negative (miss car) | `yolo_confidence=0.4` — lower if needed |
| Torch too large | Could use ONNX runtime with yolov8n.onnx instead |

## Validasi
1. `pip install ultralytics` → import works
2. Jalankan engine → log "YOLO initialized: yolov8n.pt"
3. Slot kosong tanpa kendaraan → FREE (false positive texture solved!)
4. Mobil parkir di slot → FULL
5. Motor parkir di slot → FULL
6. Slot tanpa mobil tetap FREE meski ada bayangan/tekstur
7. YOLO bounding boxes visible in overlay
8. Fallback: set `use_object_detection=false` → pixel counting still works
