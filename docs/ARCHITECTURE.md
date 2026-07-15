# ARCHITECTURE

Dokumen arsitektur sistem deteksi slot parkir.

---

## 1. Block Diagram Sistem

```
┌──────────────────────────┐
│  CCTV Dahua              │
│  RTSP H.264              │
└────────────┬─────────────┘
             │ RTSP
             ▼
┌──────────────────────────────────────────────────────────────┐
│  PC LOKAL  (Windows / Ubuntu)                                │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Detection Engine  (thread terpisah)                   │  │
│  │                                                        │  │
│  │   RTSPReader ──▶ Preprocessor ──▶ ParkingDetector     │  │
│  │        │                              │                │  │
│  │        ▼                              ▼                │  │
│  │  FrameBuffer (latest)        StateManager (in-memory)  │  │
│  │        │                     (EMA + hysteresis +       │  │
│  │        │                      manual overrides)        │  │
│  │        │                              │                │  │
│  │        │                              ▼                │  │
│  │        │                     Repository (SQLite write) │  │
│  │        │                              │                │  │
│  └────────┼──────────────────────────────┼────────────────┘  │
│           │                              │                   │
│           ▼                              ▼                   │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  FastAPI App  (port 8000)                              │  │
│  │                                                        │  │
│  │   /video_feed   /api/slots   /api/history   /ws/slots  │  │
│  │   /api/slots/{id}/override   /api/slots/overrides      │  │
│  │                                                        │  │
│  └─────────────────────────┬──────────────────────────────┘  │
│                            │                                 │
│                            ▼                                 │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  SQLite  (parking.db)                                  │  │
│  │   slots │ slot_status │ occupancy_log │ summary │ ...  │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Static Web Dashboard  (di-serve oleh FastAPI)         │  │
│  └────────────────────────────────────────────────────────┘  │
└────────────────────────────┬─────────────────────────────────┘
                             │ http://192.168.x.x:8000
                             ▼
            ┌──────────────────────────────┐
            │  HP / Laptop di Wi-Fi sama   │
            │  Browser → Dashboard         │
            └──────────────────────────────┘
```

---

## 2. Layered Architecture

```
┌────────────────────────────────────────────────┐
│  Presentation Layer                            │
│   - web/ (HTML, CSS, JS)                       │
│   - tools/parking_picker.py (desktop)          │
└─────────────────────┬──────────────────────────┘
                      │
┌─────────────────────▼──────────────────────────┐
│  API Layer                                     │
│   - app/api/  (FastAPI routes, WebSocket)      │
└─────────────────────┬──────────────────────────┘
                      │
┌─────────────────────▼──────────────────────────┐
│  Service Layer                                 │
│   - app/services/  (RTSP reader, detection     │
│     loop, frame broadcaster)                   │
└─────────────────────┬──────────────────────────┘
                      │
┌─────────────────────▼──────────────────────────┐
│  Domain / Core Layer  (pure, testable)         │
│   - app/core/  (preprocessor, detector,        │
│     geometry)                                  │
└─────────────────────┬──────────────────────────┘
                      │
┌─────────────────────▼──────────────────────────┐
│  Data Layer                                    │
│   - app/db/  (SQLAlchemy models, repository,    │
│     connection)                                │
│   - SQLite (parking.db)                        │
└────────────────────────────────────────────────┘
```

Aturan ketergantungan: **layer atas boleh import layer bawah, tidak sebaliknya**.  
Layer Core bebas dari I/O (tidak baca file, tidak query DB) — agar bisa di-unit-test cepat.

---

## 3. Modul Breakdown

### 3.1 `app/core/` — Domain logic (pure)

| File | Tanggung Jawab |
|---|---|
| `preprocessor.py` | Fungsi `preprocess(frame, ...)` — Grayscale → CLAHE opsional → Gaussian blur → threshold (manual/adaptive) → median → dilate → morphological close. Juga `compute_adaptive_threshold(frame, base_threshold)` untuk adaptive threshold based on mean brightness. |
| `detector.py` | Fungsi `detect_slot(processed, polygon, threshold, shadow_mask, min_object_area) -> (status, ratio)`. Hitung rasio piksel non-zero dalam polygon dengan shadow adjustment dan noise filter. |
| `geometry.py` | Helper polygon: bounding rect, centroid (`moments`), local point shift, fillPoly mask. |

### 3.2 `app/services/` — Orchestration

| File | Tanggung Jawab |
|---|---|
| `rtsp_reader.py` | Class `RTSPReader` — thread baca RTSP, buffer frame terbaru, auto-reconnect, event callback (RTSP disconnect/reconnect). |
| `detection_loop.py` | Loop utama: ambil frame → preprocess → detect tiap slot (EMA smoothing + hysteresis + manual override) → upsert status ke DB → broadcast WS. Juga `_draw_overlay()` untuk annotasi frame. |
| `frame_broadcaster.py` | Generator MJPEG: encode frame terbaru ke JPEG dengan overlay polygon + status. |
| `ws_manager.py` | Manager WebSocket: tracking client, broadcast event (threadsafe via queue). |

### 3.3 `app/api/` — HTTP/WebSocket

| File | Tanggung Jawab |
|---|---|
| `main.py` | Bootstrap FastAPI, mount static di `/assets`, lifespan (start/stop detection thread). |
| `routes_slots.py` | CRUD slot + override endpoints (`GET /api/slots/overrides`, `POST/DELETE /api/slots/{id}/override`). |
| `routes_video.py` | `/video_feed` MJPEG. |
| `routes_history.py` | Query log historis & summary (dengan bucketing Python + range auto-detect). |
| `routes_status.py` | `/api/status` ringkasan + `/health` health check (FPS, RTSP, DB, uptime). |
| `ws_slots.py` | Endpoint `/ws/slots` — broadcast `slot_changed`, `summary_tick`, `system_event`, ping/pong. |

### 3.4 `app/db/` — Persistence

| File | Tanggung Jawab |
|---|---|
| `connection.py` | SQLAlchemy engine + session factory (SQLite via `sqlite:///parking.db`). Baca config dari `.env`. |
| `models.py` | ORM: `Slot`, `SlotStatus`, `OccupancyLog`, `OccupancySummary`, `SystemEvent`. |
| `repository.py` | Fungsi CRUD high-level (`get_active_slots`, `upsert_status`, `log_change`, `insert_summary`, `auto_next_slot_code`, dll). |

### 3.5 `app/tools/`

| File | Tanggung Jawab |
|---|---|
| `parking_picker.py` | Refactor `ParkingSpacePicker.py`. Sumber polygon kini dari/ke SQLite via `repository`. |
| `migrate_pickle_to_mysql.py` | One-shot migrasi polygon dari file pickle `carParkPos` ke database. |
| `calibrate_threshold.py` | Tool tuning threshold interaktif: uji berbagai nilai threshold pada frame tersimpan. |

### 3.6 `app/config.py`

`pydantic-settings` mem-baca `.env` jadi objek config bertipe (RTSP, DB, threshold, port, adaptive threshold, shadow removal, morphological, logging, dll).

---

## 4. Sequence Diagram

### 4.1 Live Video Feed

```
Browser           FastAPI              FrameBroadcaster      RTSPReader
  │                 │                          │                  │
  │ GET /video_feed │                          │                  │
  ├────────────────▶│                          │                  │
  │                 │ stream JPEG generator    │                  │
  │                 ├─────────────────────────▶│                  │
  │                 │                          │  get latest frame│
  │                 │                          ├─────────────────▶│
  │                 │                          │◀─────────────────┤
  │                 │                          │ (encode + overlay)
  │                 │◀─────────────────────────┤                  │
  │◀────────────────┤  multipart/x-mixed-replace                  │
  │ (loop)          │                          │                  │
```

### 4.2 Status Update Realtime

```
DetectionLoop      Repository       WSManager        Browser(WS)
     │                 │                │                 │
     │ status changed  │                │                 │
     ├────────────────▶│ upsert_status  │                 │
     │                 ├──▶ SQLite      │                 │
     │                 │ (parking.db)   │                 │
     │ broadcast event │                │                 │
     ├──────────────────────────────────▶│                 │
     │                 │                ├ for each client│
     │                 │                ├────────────────▶│ JSON push
     │                 │                │                 │ (UI update)
```

### 4.3 Tambah Polygon (Picker)

```
ParkingPicker      Repository      SQLite
     │                 │             │
     │ user double-click             │
     │ create polygon  │             │
     ├────────────────▶│ insert slot │
     │                 ├────────────▶│
     │                 │◀────────────┤
     │◀────────────────┤ slot_id     │
     │ refresh canvas  │             │
```

---

## 5. Threading Model

```
MainThread (FastAPI / Uvicorn)
│
├── Thread-1: RTSPReader
│     └── baca frame → buffer → event callback (RTSP disconnect/reconnect)
│
├── Thread-2: DetectionLoop
│     └── preprocess → detect (EMA + hysteresis + overrides) → DB → WS broadcast
│
├── Thread-pool: Uvicorn workers (handle HTTP)
│
└── Thread: WS broadcaster (queue-based, threadsafe via ws_manager._queue)
```
1. CCTV         ──RTSP──▶  RTSPReader (thread)
2. RTSPReader   ──frame──▶ FrameBuffer (latest)
3. DetectionLoop ──pull──▶ FrameBuffer
4. DetectionLoop ──preprocess──▶ Preprocessor
5. DetectionLoop ──detect (per slot)──▶ Detector
6. DetectionLoop ──upsert──▶ Repository ──▶ SQLite
7. DetectionLoop ──on change──▶ WSManager ──▶ Browser (WS)
8. Browser      ──GET /video_feed──▶ FrameBroadcaster
9. FrameBroadcaster ──pull──▶ FrameBuffer ──▶ JPEG ──▶ Browser
```

---

## 7. Use Case Diagram (ringkasan)

```
                ┌──────────────┐
                │   Admin      │
                └──────┬───────┘
                       │
      ┌────────────────┼────────────────┐
      │                │                │
      ▼                ▼                ▼
 [Kalibrasi      [Lihat Status     [Lihat Log
  Polygon]        Realtime]         Historis]
                       ▲
                       │
                ┌──────┴───────┐
                │  Pengunjung  │
                └──────────────┘
```

| Aktor | Use Case |
|---|---|
| Admin | Kalibrasi polygon, lihat status, lihat log, ekspor data |
| Pengunjung | Lihat status realtime (read-only) |

---

## 8. Konfigurasi Runtime

Semua konfigurasi via `.env` (di-load oleh `app/config.py`).

```env
# RTSP
RTSP_URL=rtsp://admin:xxx@IP_CCTV:554/cam/realmonitor?channel=1&subtype=0

# Detection
DETECTION_THRESHOLD=0.22
DETECTION_HYSTERESIS_MARGIN=0.03
RATIO_EMA_ALPHA=0.70
FRAME_WIDTH=1280
FRAME_HEIGHT=720
DETECT_INTERVAL_MS=200
SUMMARY_INTERVAL_SEC=60

# Preprocessing
PREPROCESS_THRESHOLD_MODE=adaptive       # manual | adaptive
PREPROCESS_USE_CLAH= true
PREPROCESS_MANUAL_THRESHOLD=150
PREPROCESS_ADAPTIVE_C=7

# Shadow Removal
REMOVE_SHADOWS=false
SHADOW_V_LOW=0
SHADOW_V_HIGH=45

# Adaptive Threshold (lighting-aware)
ADAPTIVE_THRESHOLD_ENABLED=true
ADAPTIVE_THRESHOLD_MIN=0.20
ADAPTIVE_THRESHOLD_MAX=0.35

# Morphological
CLOSE_KSIZE=3
DILATE_ITERATIONS=1

# Noise Filter
MIN_OBJECT_AREA=200

# Database (SQLite default)
DATABASE_URL=sqlite:///parking.db

# API
API_HOST=0.0.0.0
API_PORT=8000

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/app.log
```

---

## 9. Flowchart Algoritma Deteksi

```
       ┌─────────────────┐
       │  Mulai loop     │
       └────────┬────────┘
                │
                ▼
       ┌─────────────────┐
       │ Ambil frame     │
       │ (skip lama)     │
       └────────┬────────┘
                │
                ▼
       ┌─────────────────┐
       │ Resize 1280x720 │
       └────────┬────────┘
                │
                ▼
       ┌─────────────────┐
       │ CLAHE (opsional)│
       └────────┬────────┘
                ▼
       ┌─────────────────┐
       │ Grayscale       │
       └────────┬────────┘
                ▼
       ┌─────────────────┐
       │ Gaussian Blur   │
       └────────┬────────┘
                ▼
       ┌───────────────────────────────┐
       │ Threshold (manual/adaptive)   │
       │ Bisa shadow removal opsional  │
       └────────┬──────────────────────┘
                ▼
       ┌─────────────────┐
       │ Median Blur     │
       └────────┬────────┘
                ▼
       ┌─────────────────┐
       │ Dilate          │
       └────────┬────────┘
                ▼
       ┌─────────────────┐
       │ Morphological   │
       │ Close           │
       └────────┬────────┘
                │
                ▼
       ┌─────────────────────────┐
       │ Hitung adaptive TH      │
       │ (mean brightness based) │
       └────────┬────────────────┘
                │
                ▼
       ┌─────────────────────────┐
       │ Untuk tiap polygon slot │
       └────────┬────────────────┘
                ▼
       ┌───────────────────────────────┐
       │ Manual override aktif?        │
       └─┬──────────────────────────┬──┘
       ya│                          │tidak
         ▼                          ▼
    [pakai status        ┌─────────────────────────┐
     override]           │ Crop ROI + mask polygon │
         │               └────────┬────────────────┘
         │                        ▼
         │               ┌─────────────────────────┐
         │               │ ratio = nonZero / area  │
         │               │ - shadow adjustment     │
         │               │ - min_object_area filter│
         │               └────────┬────────────────┘
         │                        ▼
         │               ┌────────────────────┐
         │               │ EMA smoothing      │
         │               │ ratio_ema[slot]    │
         │               └────────┬───────────┘
         │                        ▼
         │                ┌───────┴────────┐
         │                │ Hysteresis     │
         │                │ FREE↔FULL      │
         │                │ dengan margin  │
         │                └───────┬────────┘
         │                        │
         └──────────┬─────────────┘
                    ▼
        ┌───────────┴───────────┐
        │ Status berubah?       │
        │ (vs previous stable)  │
        └─┬──────────────────┬──┘
       ya│                  │tidak
         ▼                  ▼
  ┌────────────────┐   ┌────────────────┐
  │ Insert log     │   │ Skip (noop)    │
  │ Broadcast WS   │   └───────┬────────┘
  └───────┬────────┘           │
          │                    │
          ▼                    ▼
       ┌───────────────────────────┐
       │ Upsert slot_status +      │
       │ summary periodik (60s)    │
       └────────┬──────────────────┘
                │
                ▼
       ┌─────────────────┐
       │ Buat overlay    │
       │ (poligon + label)│
       └────────┬────────┘
                │
                ▼
       ┌─────────────────┐
       │ Lanjut frame    │
       └─────────────────┘
```
