# ARCHITECTURE

Dokumen arsitektur sistem deteksi slot parkir.

---

## 1. Block Diagram Sistem

```
┌──────────────────────────┐
│  CCTV Dahua              │
│  192.168.18.155          │
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
│  │        │                              │                │  │
│  │        │                              ▼                │  │
│  │        │                     Repository (MySQL write)  │  │
│  │        │                              │                │  │
│  └────────┼──────────────────────────────┼────────────────┘  │
│           │                              │                   │
│           ▼                              ▼                   │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  FastAPI App  (port 8000)                              │  │
│  │                                                        │  │
│  │   /video_feed   /api/slots   /api/history   /ws/slots  │  │
│  │                                                        │  │
│  └─────────────────────────┬──────────────────────────────┘  │
│                            │                                 │
│                            ▼                                 │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  MySQL 8  (port 3306)                                  │  │
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
│   - app/db/  (SQLAlchemy models, repository,   │
│     connection)                                │
│   - MySQL                                      │
└────────────────────────────────────────────────┘
```

Aturan ketergantungan: **layer atas boleh import layer bawah, tidak sebaliknya**.  
Layer Core bebas dari I/O (tidak baca file, tidak query DB) — agar bisa di-unit-test cepat.

---

## 3. Modul Breakdown

### 3.1 `app/core/` — Domain logic (pure)

| File | Tanggung Jawab |
|---|---|
| `preprocessor.py` | Fungsi `preprocess(frame) -> processed`. Grayscale → blur → threshold → median → dilate. |
| `detector.py` | Fungsi `detect_slot(processed, polygon, threshold) -> (status, ratio)`. Hitung rasio piksel non-zero dalam polygon. |
| `geometry.py` | Helper polygon: bounding rect, centroid (`moments`), local point shift, fillPoly mask. |

### 3.2 `app/services/` — Orchestration

| File | Tanggung Jawab |
|---|---|
| `rtsp_reader.py` | Class `RTSPReader` — thread baca RTSP, buffer frame terbaru, auto-reconnect. |
| `detection_loop.py` | Loop utama: ambil frame → preprocess → detect tiap slot → push status ke DB & WS broadcaster. |
| `frame_broadcaster.py` | Generator MJPEG: encode frame terbaru ke JPEG dengan overlay polygon + status. |
| `ws_manager.py` | Manager WebSocket: tracking client, broadcast event. |

### 3.3 `app/api/` — HTTP/WebSocket

| File | Tanggung Jawab |
|---|---|
| `main.py` | Bootstrap FastAPI, mount static, lifespan (start/stop detection thread). |
| `routes_slots.py` | CRUD slot. |
| `routes_video.py` | `/video_feed` MJPEG. |
| `routes_history.py` | Query log historis & summary. |
| `ws_slots.py` | Endpoint `/ws/slots`. |

### 3.4 `app/db/` — Persistence

| File | Tanggung Jawab |
|---|---|
| `connection.py` | SQLAlchemy engine + session factory. Baca config dari `.env`. |
| `models.py` | ORM: `Slot`, `SlotStatus`, `OccupancyLog`, `OccupancySummary`, `SystemEvent`. |
| `repository.py` | Fungsi CRUD high-level (mis. `upsert_status`, `log_change`). |
| `schema.sql` | Raw DDL untuk dokumentasi & import manual. |

### 3.5 `app/tools/`

| File | Tanggung Jawab |
|---|---|
| `parking_picker.py` | Refactor `ParkingSpacePicker.py`. Sumber polygon kini dari/ke MySQL via `repository`. |

### 3.6 `app/config.py`

`pydantic-settings` mem-baca `.env` jadi objek config bertipe (RTSP, DB, threshold, port, dll).

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
     │                 ├──▶ MySQL       │                 │
     │                 │                │                 │
     │ broadcast event │                │                 │
     ├──────────────────────────────────▶│                 │
     │                 │                ├ for each client│
     │                 │                ├────────────────▶│ JSON push
     │                 │                │                 │ (UI update)
```

### 4.3 Tambah Polygon (Picker)

```
ParkingPicker      Repository      MySQL
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

| Thread | Loop | Catatan |
|---|---|---|
| Main / asyncio | FastAPI + WebSocket | Tidak boleh blocking |
| `RTSPReader` thread | Baca frame terus, simpan ke buffer | Daemon thread |
| `DetectionLoop` thread | Tiap N ms ambil frame dari buffer, deteksi, tulis DB, broadcast WS | Daemon thread |

Komunikasi antar thread:
- `RTSPReader` → `DetectionLoop`: lewat lock + variabel frame terbaru.
- `DetectionLoop` → `WSManager`: lewat asyncio queue (thread-safe).

---

## 6. Data Flow

```
1. CCTV         ──RTSP──▶  RTSPReader (thread)
2. RTSPReader   ──frame──▶ FrameBuffer (latest)
3. DetectionLoop ──pull──▶ FrameBuffer
4. DetectionLoop ──preprocess──▶ Preprocessor
5. DetectionLoop ──detect (per slot)──▶ Detector
6. DetectionLoop ──upsert──▶ Repository ──▶ MySQL
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
RTSP_URL=rtsp://admin:xxx@192.168.18.155:554/cam/realmonitor?channel=1&subtype=0

# Detection
DETECTION_THRESHOLD=0.18
FRAME_WIDTH=1280
FRAME_HEIGHT=720
DETECT_INTERVAL_MS=200

# MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=parking_user
MYSQL_PASSWORD=parking_pass
MYSQL_DATABASE=parking_db

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
       │ Grayscale       │
       └────────┬────────┘
                ▼
       ┌─────────────────┐
       │ Gaussian Blur   │
       └────────┬────────┘
                ▼
       ┌─────────────────┐
       │ Threshold INV   │
       └────────┬────────┘
                ▼
       ┌─────────────────┐
       │ Median Blur     │
       └────────┬────────┘
                ▼
       ┌─────────────────┐
       │ Dilate          │
       └────────┬────────┘
                │
                ▼
       ┌─────────────────────────┐
       │ Untuk tiap polygon slot │
       └────────┬────────────────┘
                ▼
       ┌─────────────────────────┐
       │ Crop ROI + mask polygon │
       └────────┬────────────────┘
                ▼
       ┌─────────────────────────┐
       │ ratio = nonZero / area  │
       └────────┬────────────────┘
                ▼
        ┌──────┴───────┐
        │ ratio < TH ? │
        └─┬──────────┬─┘
       ya │          │ tidak
          ▼          ▼
       FREE        FULL
          │          │
          └────┬─────┘
               ▼
       ┌─────────────────┐
       │ Update DB + WS  │
       └────────┬────────┘
               │
               ▼
       ┌─────────────────┐
       │ Lanjut frame    │
       └─────────────────┘
```
