# FOLDER STRUCTURE

Struktur folder target setelah selesai implementasi.

---

## 1. Pohon Lengkap

```
TA_OpenCV/
│
├── app/                                # Source code Python utama
│   ├── __init__.py
│   ├── config.py                       # pydantic-settings (.env loader)
│   │
│   ├── core/                           # Domain logic (pure, tidak ada I/O)
│   │   ├── __init__.py
│   │   ├── preprocessor.py             # gray → blur → threshold → morfologi
│   │   ├── detector.py                 # detect_slot(processed, polygon, threshold)
│   │   └── geometry.py                 # bounding rect, centroid, mask helper
│   │
│   ├── services/                       # Orchestration & I/O long-running
│   │   ├── __init__.py
│   │   ├── rtsp_reader.py              # Thread baca RTSP + auto-reconnect
│   │   ├── detection_loop.py           # Pipeline utama (EMA + hysteresis + override)
│   │   ├── frame_broadcaster.py        # MJPEG generator (encode + overlay)
│   │   └── ws_manager.py               # WebSocket connection manager
│   │
│   ├── api/                            # FastAPI routes
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI app + lifespan + mount static
│   │   ├── schemas.py                  # Pydantic models (SlotIn, SlotOut, ...)
│   │   ├── routes_slots.py             # /api/slots CRUD + manual override
│   │   ├── routes_video.py             # /video_feed MJPEG
│   │   ├── routes_history.py           # /api/history, /api/summary
│   │   ├── routes_status.py            # /api/status, /health
│   │   └── ws_slots.py                 # /ws/slots WebSocket endpoint
│   │
│   ├── db/                             # Persistence layer
│   │   ├── __init__.py
│   │   ├── connection.py               # SQLAlchemy engine + SessionLocal (SQLite)
│   │   ├── models.py                   # ORM: Slot, SlotStatus, OccupancyLog, ...
│   │   └── repository.py               # CRUD high-level functions
│   │
│   └── tools/                          # Standalone utilities
│       ├── __init__.py
│       ├── parking_picker.py           # Refactor ParkingSpacePicker.py
│       ├── migrate_pickle_to_mysql.py  # One-shot migration pickle → DB
│       └── calibrate_threshold.py      # Tool tuning threshold interaktif
│
├── web/                                # Frontend statis (no build tool)
│   ├── index.html                      # Dashboard utama
│   ├── admin.html                      # Halaman admin (opsional)
│   ├── css/
│   │   └── style.css                   # Custom override Tailwind (+ .btn-override)
│   └── js/
│       └── dashboard.js                # Logic dashboard (fetch + WS + overrides)
│
├── dataset/                            # Dataset PKLot untuk pengujian akurasi
│   ├── pklot/                          # Folder dataset PKLot
│   ├── ground_truth.json               # Ground truth labels
│   ├── polygons.json                   # Polygon definitions
│   └── finalize_dataset.py             # Script finalisasi dataset
│
├── docs/                               # Dokumentasi proyek
│   ├── PLANNING.md                     # Dokumen induk perencanaan
│   ├── REQUIREMENTS.md                 # FR + NFR
│   ├── ARCHITECTURE.md                 # Diagram & breakdown modul
│   ├── DATABASE.md                     # Skema SQLite + ERD + query
│   ├── API.md                          # Spesifikasi REST + WebSocket
│   ├── ROADMAP.md                      # Timeline pengerjaan
│   ├── FOLDER_STRUCTURE.md             # File ini
│   ├── INSTALL.md                      # Panduan instalasi
│   ├── README.md                       # Index dokumentasi
├──
├── tests/                              # Unit & integration tests
│   ├── __init__.py
│   ├── test_preprocessor.py
│   ├── test_detector.py
│   └── test_geometry.py
│
├── logs/                               # Log runtime (di-gitignore)
│   └── app.log
│
├── .env                                # Konfigurasi (DI-GITIGNORE!)
├── .gitignore
├── .python-version                     # Pin Python 3.11 (untuk pyenv)
├── requirements.txt                    # Dependency Python
├── pytest.ini                          # Config pytest
├── README.md                           # Overview proyek + quickstart
├──
├── parking.db                          # SQLite database (auto-generated)
├── run_server.py                       # Entry: python run_server.py
├── run_engine.py                       # Entry: detection only (headless)
├── run_picker.py                       # Entry: tool kalibrasi polygon
└── test.py                             # Prototipe testing cepat
```

---

## 2. Penjelasan Folder

### `app/`
Seluruh source code Python aplikasi. Dipecah berdasarkan **layer arsitektur** (lihat `ARCHITECTURE.md`).

| Subfolder | Layer | Sifat |
|---|---|---|
| `core/` | Domain | Pure, no I/O, mudah di-unit-test |
| `services/` | Service | Long-running, threaded |
| `api/` | Presentation (HTTP) | Stateless route handler |
| `db/` | Data | ORM + repository |
| `tools/` | CLI/Desktop | Script standalone |

### `web/`
Frontend statis. **Tidak butuh Node.js**. Dilayani langsung oleh FastAPI via `StaticFiles` di path `/assets`.

### `dataset/`
Dataset PKLot untuk pengujian akurasi deteksi. Berisi ground truth, polygon definitions, dan script finalisasi.

### `data/`
Data lokal: file pickle warisan, frame sample untuk test. Tabel utama tetap di SQLite.

### `docs/`
Semua dokumentasi proyek. Ditulis Markdown agar mudah dibaca di GitHub maupun VS Code.

### `tests/`
Unit & integration test. Mengikuti konvensi `test_*.py` agar `pytest` auto-discover.

### `logs/`
Output log runtime (`app.log`, dll). Di-`.gitignore`.

### `parking.db`
Database SQLite — auto-generated saat pertama `run_server.py` dijalankan. Tidak perlu setup MySQL.

---

## 3. Entry Point

| File | Tujuan |
|---|---|
| `run_server.py` | Start FastAPI + detection thread (mode normal produksi) |
| `run_engine.py` | Start detection loop saja, tanpa API (debug pipeline) |
| `run_picker.py` | Buka window kalibrasi polygon (admin) |

Contoh `run_server.py`:
```python
import uvicorn
from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )
```

---

## 4. Catatan

- `parking.db` ada di `.gitignore` (tidak di-commit) karena berisi data runtime.
- Database dibuat otomatis; cukup hapus file untuk reset.
- `data/` dan `legacy/` tidak ada di proyek saat ini — referensi dari dokumentasi awal.

---

## 5. Mapping File Lama → File Baru

| File lama | File baru | Catatan |
|---|---|---|
| `main.py` | dipecah ke `app/core/preprocessor.py`, `app/core/detector.py`, `app/services/detection_loop.py`, `app/services/rtsp_reader.py` | Loop, threading, dan I/O dipisah |
| `ParkingSpacePicker.py` | `app/tools/parking_picker.py` | Sumber data: pickle → MySQL |
| `rtsp_check.py` | tetap di root sebagai utilitas | Atau pindah ke `app/tools/rtsp_check.py` |
| `test.py` | duplikat `main.py`, dihapus | Diganti `tests/` (pytest) |
| `CarParkPos` | `data/CarParkPos` | Sumber awal migrasi |
| `img.png` | dipindah ke `docs/diagrams/` bila relevan | Atau hapus |

---

## 6. Naming Convention

| Item | Konvensi | Contoh |
|---|---|---|
| Module file | `snake_case.py` | `detection_loop.py` |
| Class | `PascalCase` | `RTSPReader` |
| Function | `snake_case` | `detect_slot()` |
| Constant | `UPPER_SNAKE` | `DETECTION_THRESHOLD` |
| Slot code | `[A-Z][0-9]+` atau `S###` | `A1`, `S001` |
| Tabel DB | `snake_case` | `occupancy_log` |
| API path | `kebab-case` (atau snake) | `/api/slots`, `/video_feed` |
| Branch git | `feature/<topic>` | `feature/db-layer` |

---

## 7. Aturan Import

Hindari circular import dengan urutan:

```
config  ←  db  ←  core  ←  services  ←  api
                           ↑
                         tools
```

- `core` boleh di-import siapa saja, tapi tidak boleh import dari `services`/`api`/`db`.
- `db` boleh diakses dari `services`, `api`, `tools`.
- `services` diakses dari `api` saja.
- `api` adalah lapisan paling luar, tidak diakses internal lain.
