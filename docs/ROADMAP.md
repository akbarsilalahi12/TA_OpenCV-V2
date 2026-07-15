# ROADMAP

Timeline pengerjaan dari prototipe `main.py` ke sistem terintegrasi.

> **Estimasi total: ~10 hari kerja** (bisa lebih cepat bila fokus penuh).

---

## 1. Ringkasan Fase

| Fase | Nama | Durasi | Output Utama |
|---|---|---|---|
| 0 | Setup environment | 0.5 hari | Tools siap (Python, MySQL, Git) |
| 1 | Refactor core | 1 hari | `app/core/` lulus unit test |
| 2 | Database layer | 1 hari | SQLite + ORM + migrasi pickle |
| 3 | Service & detection loop | 1 hari | Pipeline berjalan headless |
| 4 | Backend API (FastAPI) | 1.5 hari | REST + MJPEG + WebSocket |
| 5 | Web dashboard | 2 hari | Halaman live + chart |
| 6 | Tool picker (refactor) | 0.5 hari | Picker terhubung MySQL |
| 7 | Testing & tuning | 1 hari | Hasil pengujian akurasi |
| 8 | Dokumentasi | 1.5 hari | Semua file di `docs/` lengkap |

---

## 2. Detail Per Fase

### Fase 0 — Setup Environment (0.5 hari)

**Tujuan:** semua tools siap di mesin developer.

**Tugas:**
- [ ] Install Python 3.11
- [ ] Install MySQL Server 8 (atau XAMPP)
- [ ] Buat virtual environment: `python -m venv venv`
- [ ] Install dependency awal: `pip install -r requirements.txt`
- [ ] Buat database & user MySQL (lihat `DATABASE.md` §6)
- [ ] Copy `.env.example` ke `.env`, isi sesuai lokal
- [ ] Pastikan `python rtsp_check.py "<RTSP_URL>"` mengembalikan `isOpened True`

**Definition of Done:** `python -c "import cv2, fastapi, sqlalchemy, pymysql"` jalan tanpa error.

---

### Fase 1 — Refactor Core (1 hari)

**Tujuan:** pisahkan logika OpenCV dari `main.py` menjadi modul kecil yang bisa di-unit-test.

**Tugas:**
- [ ] Buat `app/core/preprocessor.py` dengan fungsi `preprocess(frame) -> np.ndarray`
- [ ] Buat `app/core/geometry.py` (bounding rect, centroid, mask polygon)
- [ ] Buat `app/core/detector.py` dengan fungsi `detect_slot(processed, polygon, threshold) -> (status, ratio)`
- [ ] Tulis unit test `tests/test_detector.py` minimal 5 kasus (slot kosong, slot terisi, polygon kecil, edge case area=0, polygon di luar frame)
- [ ] Jalankan: `pytest tests/`

**Definition of Done:** semua test hijau, coverage core ≥ 60%.

---

### Fase 2 — Database Layer (1 hari)

**Tujuan:** SQLite siap menyimpan polygon & status.

**Tugas:**
- [ ] Buat `app/db/connection.py` (SQLAlchemy engine + session factory, SQLite)
- [ ] Buat `app/db/models.py` untuk 5 tabel (`Slot`, `SlotStatus`, `OccupancyLog`, `OccupancySummary`, `SystemEvent`)
- [ ] Buat `app/db/repository.py` (helper: `get_active_slots`, `upsert_status`, `log_change`, `insert_summary`)
- [ ] Buat `app/tools/migrate_pickle_to_mysql.py` untuk import data lama
- [ ] Verifikasi: jalankan migrasi, lalu `SELECT * FROM slots`

**Definition of Done:** data dari `CarParkPos` (pickle) sudah ada di tabel `slots`.

---

### Fase 3 — Service & Detection Loop (1 hari)

**Tujuan:** pipeline lengkap (RTSP → preprocess → detect → MySQL) jalan headless tanpa GUI.

**Tugas:**
- [ ] Buat `app/services/rtsp_reader.py` (thread, buffer frame terbaru, auto-reconnect)
- [ ] Buat `app/services/detection_loop.py` (orchestrator)
- [ ] Tulis status terkini ke `slot_status` (upsert)
- [ ] Tulis log ke `occupancy_log` saat status berubah
- [ ] Tulis snapshot ke `occupancy_summary` tiap 60 detik
- [ ] Tulis event ke `system_event` saat reconnect
- [ ] Buat `run_engine.py` sebagai entry point standalone

**Definition of Done:** jalankan `python run_engine.py` selama 5 menit, `SELECT * FROM slot_status` menunjukkan timestamp ter-update.

---

### Fase 4 — Backend API (FastAPI) (1.5 hari)

**Tujuan:** API REST + WebSocket + MJPEG siap.

**Tugas:**
- [ ] Buat `app/config.py` (pydantic-settings)
- [ ] Buat `app/api/main.py` (FastAPI bootstrap + lifespan)
- [ ] Implement `app/api/routes_slots.py` (GET/POST/PUT/DELETE)
- [ ] Implement `app/api/routes_video.py` (`/video_feed` MJPEG)
- [ ] Implement `app/api/routes_history.py` (history + summary)
- [ ] Implement `app/api/ws_slots.py` (WebSocket manager + broadcast)
- [ ] Implement `/health` endpoint
- [ ] Tambah `app/services/frame_broadcaster.py` (encode JPEG dengan overlay)

**Definition of Done:**
- Buka `http://localhost:8000/docs` → semua endpoint muncul di Swagger
- `curl /api/slots` mengembalikan data
- `<img src="/video_feed">` di HTML kosong menampilkan video

---

### Fase 5 — Web Dashboard (2 hari)

**Tujuan:** halaman web siap pakai untuk demo.

**Tugas:**
- [ ] Buat `web/index.html` (Tailwind CDN + Chart.js CDN)
- [ ] Layout: header counter besar, video di tengah, grid slot di kanan, chart di bawah
- [ ] Buat `web/js/dashboard.js` (fetch awal + WebSocket subscribe)
- [ ] Implementasi update grid slot via WebSocket
- [ ] Implementasi chart historis dari `/api/summary?range=24h`
- [ ] Mobile responsive (Tailwind `md:` / `lg:` breakpoint)
- [ ] Buat `web/admin.html` (opsional) untuk list/edit slot
- [ ] Mount static di FastAPI: `app.mount("/", StaticFiles(directory="web", html=True))`

**Definition of Done:**
- Buka dari laptop server: `http://localhost:8000` → tampil lengkap
- Buka dari HP di Wi-Fi sama: `http://192.168.x.x:8000` → tampil lengkap
- Status berubah di video tampil di grid slot < 1 detik

---

### Fase 6 — Tool Picker (Refactor) (0.5 hari)

**Tujuan:** picker tidak lagi pakai pickle, langsung ke MySQL.

**Tugas:**
- [ ] Pindahkan `ParkingSpacePicker.py` ke `app/tools/parking_picker.py`
- [ ] Ganti load/save pickle menjadi panggilan `repository.list_slots()` / `create_slot()` / `update_slot()` / `delete_slot()`
- [ ] Tambah dialog input untuk `slot_code` saat tambah polygon (atau auto-generate `S001`, `S002`, ...)
- [ ] Tetap pakai `cv2` window, tinggal sumber data berbeda

**Definition of Done:** drag/resize/add/delete polygon di picker langsung tercermin di tabel `slots` MySQL.

---

### Fase 7 — Testing & Tuning (1 hari)

**Tujuan:** sistem terbukti memenuhi NFR akurasi & performance.

**Tugas:**
- [ ] Siapkan dataset uji: minimal 30 sampel skenario (slot kosong vs terisi)
- [ ] Catat hasil di tabel: `Slot | Aktual | Sistem | Match?`
- [ ] Hitung **Accuracy, Precision, Recall, F1**
- [ ] Tuning `DETECTION_THRESHOLD` (coba 0.15 / 0.18 / 0.22)
- [ ] Uji kondisi: siang terang, mendung, malam (lampu)
- [ ] Ukur **FPS** dengan hitung frame per detik di detection loop
- [ ] Ukur **latency** WS: timestamp deteksi vs timestamp diterima browser
- [ ] Uji **reliability**: cabut & sambung kabel CCTV → harus auto-reconnect

**Definition of Done:** dokumentasi `docs/TESTING.md` berisi tabel hasil dan plot/chart.

---

### Fase 8 — Dokumentasi (1.5 hari)

**Tujuan:** semua dokumen siap untuk sidang TA.

**Tugas:**
- [ ] Lengkapi `docs/INSTALL.md` (langkah-by-langkah dari nol)
- [ ] Lengkapi `docs/USER_MANUAL.md` (cara pakai picker, dashboard, troubleshoot)
- [ ] Buat `docs/TESTING.md` (hasil pengujian dari Fase 7)
- [ ] Buat diagram di draw.io / Mermaid:
  - [ ] Block diagram sistem → `docs/diagrams/system_architecture.png`
  - [ ] Flowchart algoritma deteksi → `docs/diagrams/flowchart_detection.png`
  - [ ] Use case diagram → `docs/diagrams/use_case.png`
  - [ ] ERD database → `docs/diagrams/erd.png`
  - [ ] Sequence diagram → `docs/diagrams/sequence_video.png`
- [ ] Update `README.md` di root (overview + quickstart + screenshot)
- [ ] Pastikan `.env` di-`.gitignore`, hanya commit `.env.example`
- [ ] Final commit + push ke GitHub

**Definition of Done:** repo bersih, README menarik, semua link diagram bekerja, sistem reproducible dari clone awal.

---

## 3. Timeline Visual (Gantt sederhana)

```
Hari    1   2   3   4   5   6   7   8   9   10
       |---|---|---|---|---|---|---|---|---|---|
F0     |▓▓ |
F1     |  ▓|▓▓ |
F2     |   |  ▓|▓▓▓|
F3     |   |   |   |▓▓▓|
F4     |   |   |   |   |▓▓▓|▓▓ |
F5     |   |   |   |   |   |  ▓|▓▓▓|▓▓ |
F6     |   |   |   |   |   |   |   |  ▓|▓ |
F7     |   |   |   |   |   |   |   |   |▓▓▓|
F8     |   |   |   |   |   |   |   |   |   |▓▓▓|
```

(F = Fase. Block ▓ = aktif. Boleh paralelkan dokumentasi sambil coding fase berikutnya.)

---

## 4. Dependency Antar Fase

```
F0 → F1 → F2 → F3 → F4 → F5
                         ↓
                         F6 (paralel ringan)
                         ↓
                         F7 → F8
```

Fase 6 (picker) bisa dikerjakan paralel dengan Fase 5 karena sudah punya layer DB.

---

## 5. Risiko & Buffer

| Risiko | Probabilitas | Buffer |
|---|---|---|
| Database setup | Rendah | SQLite, zero setup |
| RTSP intermittent | Sedang | +0.5 hari di Fase 3 (auto-reconnect tuning) |
| Threshold tidak akurat di malam hari | Tinggi | +0.5 hari di Fase 7 |
| Mobile layout pecah | Rendah | +0.5 hari di Fase 5 |

**Total dengan buffer: ~12 hari kerja.**

---

## 6. Milestone Demo

| Milestone | Setelah | Demo-able |
|---|---|---|
| **M1** | Fase 3 | Pipeline jalan, data masuk MySQL (demo via SQL Workbench) |
| **M2** | Fase 4 | API + Swagger + video feed di browser |
| **M3** | Fase 5 | Dashboard lengkap, akses dari HP |
| **M4** | Fase 7 | Hasil pengujian akurasi tabel + chart |
| **M5** | Fase 8 | Sistem siap sidang, dokumentasi lengkap |

Disarankan setelah tiap milestone, lakukan **commit + push** dan **demo singkat ke pembimbing**.
