# Sistem Deteksi Slot Parkir berbasis OpenCV

Tugas Akhir — sistem deteksi okupansi slot parkir secara real-time dari CCTV RTSP, menggunakan **OpenCV** (image processing klasik) dengan output **web dashboard** yang menampilkan live video, status tiap slot, dan riwayat okupansi.

---

## Fitur

- ✅ Auto-reconnect RTSP CCTV (Dahua/standar)
- ✅ Deteksi slot via polygon ROI + rasio piksel (no ML, ringan)
- ✅ Penyimpanan ke **MySQL 8** (slot, status, log historis, summary)
- ✅ **REST API** + **WebSocket** + **MJPEG** stream (FastAPI)
- ✅ **Web dashboard** responsive (Vanilla JS + Tailwind + Chart.js)
- ✅ Tool desktop untuk kalibrasi polygon
- ✅ Konfigurasi via `.env`, kredensial tidak di-hardcode

## Arsitektur

```
CCTV (RTSP) ──▶ RTSPReader ──▶ Preprocessor ──▶ ParkingDetector
                                                      │
                                                      ▼
                                              MySQL ◀──── Repository
                                                      │
                                                      ▼
                                  FastAPI (REST + WS + MJPEG)
                                                      │
                                                      ▼
                            Web Dashboard di Browser (LAN)
```

Semua jalan di **satu PC lokal**. Dashboard dapat diakses dari HP/laptop di Wi-Fi yang sama.

---

## Stack

- Python 3.11 · OpenCV 4.10 · NumPy
- FastAPI · Uvicorn · WebSocket · MJPEG
- MySQL 8 · SQLAlchemy 2 · PyMySQL
- Vanilla JS · Tailwind CSS (CDN) · Chart.js (CDN)
- pytest

---

## Quickstart

```bash
# 1. Clone & install
git clone https://github.com/sahabiard/TA_OpenCV.git
cd TA_OpenCV
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# 2. Setup MySQL
mysql -u root -p < app/db/schema.sql
# Lalu buat user parking_user (lihat docs/INSTALL.md §4)

# 3. Konfigurasi
copy .env.example .env         # Windows
# edit .env — isi RTSP_URL & kredensial MySQL Anda

# 4. (opsional) Migrasi polygon lama dari pickle
python -m app.tools.migrate_pickle_to_mysql CarParkPos

# 5. Kalibrasi polygon
python run_picker.py

# 6. Jalankan server
python run_server.py
```

Dashboard:
- Lokal: <http://localhost:8000>
- LAN  : `http://<IP-PC>:8000`
- API docs: <http://localhost:8000/docs>

Panduan lengkap & troubleshoot: [docs/INSTALL.md](docs/INSTALL.md).

---

## Struktur Folder

```
app/
├── core/         # Domain logic murni (preprocessor, detector, geometry)
├── services/     # RTSP reader, detection loop, MJPEG, WS manager
├── api/          # FastAPI routes (slots, video, history, ws, status)
├── db/           # SQLAlchemy models + repository + schema.sql
└── tools/        # Picker desktop + migrasi pickle
web/              # Static dashboard (HTML + JS + CSS)
docs/             # Planning, requirements, arsitektur, DB, API, dll
tests/            # Unit test (pytest)
```

Detail: [docs/FOLDER_STRUCTURE.md](docs/FOLDER_STRUCTURE.md).

---

## Endpoint Utama

| Method | Path | Fungsi |
|---|---|---|
| GET | `/`             | Dashboard |
| GET | `/admin`        | Halaman admin |
| GET | `/video_feed`   | MJPEG stream |
| GET | `/api/slots`    | Daftar slot + status |
| POST/PUT/DELETE | `/api/slots[/id]` | CRUD slot |
| GET | `/api/status`   | Ringkasan free/full/total |
| GET | `/api/history`  | Log historis |
| GET | `/api/summary`  | Data agregat untuk chart |
| WS  | `/ws/slots`     | Push realtime |
| GET | `/health`       | Health check |
| GET | `/docs`         | Swagger UI |

Spesifikasi lengkap: [docs/API.md](docs/API.md).

---

## Dokumentasi

| File | Isi |
|---|---|
| [docs/PLANNING.md](docs/PLANNING.md) | Latar belakang, tujuan, deliverables, kriteria sukses |
| [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) | 38 FR + 21 NFR |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Diagram, breakdown modul, sequence, threading |
| [docs/DATABASE.md](docs/DATABASE.md) | Skema MySQL + ERD + query contoh |
| [docs/API.md](docs/API.md) | REST + WebSocket spec |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Timeline 9 fase |
| [docs/FOLDER_STRUCTURE.md](docs/FOLDER_STRUCTURE.md) | Struktur folder |
| [docs/INSTALL.md](docs/INSTALL.md) | Panduan instalasi |

---

## Test

```bash
pytest
```

Coverage core (preprocessor, detector, geometry) ditargetkan ≥ 60%.

---

## Lisensi

Proyek Tugas Akhir.
