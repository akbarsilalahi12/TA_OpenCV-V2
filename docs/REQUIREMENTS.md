# REQUIREMENTS

Daftar kebutuhan sistem deteksi slot parkir berbasis OpenCV.  
Setiap requirement diberi kode unik agar bisa dirujuk di laporan TA dan pengujian.

---

## 1. Functional Requirements (FR)

### 1.1 Akuisisi Video

| Kode | Requirement | Prioritas |
|---|---|---|
| FR-01 | Sistem dapat membuka stream RTSP H.264 dari CCTV Dahua | Wajib |
| FR-02 | Sistem melakukan reconnect otomatis bila stream RTSP putus | Wajib |
| FR-03 | Sistem membuang frame lama (`grab()`) untuk meminimalisir lag | Wajib |
| FR-04 | URL RTSP dikonfigurasi via file `.env`, bukan hardcoded | Wajib |
| FR-04a | Admin dapat override manual status slot via dashboard (FREE/FULL/Auto) | Opsional |

### 1.2 Deteksi Slot

| Kode | Requirement | Prioritas |
|---|---|---|
| FR-05 | Sistem melakukan preprocessing: grayscale → Gaussian blur → threshold inversi → median blur → dilasi | Wajib |
| FR-06 | Sistem menghitung rasio piksel non-zero di dalam polygon ROI tiap slot | Wajib |
| FR-07 | Sistem menentukan status `FREE` atau `FULL` berdasarkan threshold rasio yang dapat dikonfigurasi | Wajib |
| FR-07a | Sistem menggunakan EMA smoothing untuk mengurangi noise frame-to-frame | Wajib |
| FR-07b | Sistem menggunakan hysteresis threshold (margin +/-) untuk mencegah flicker status | Wajib |
| FR-07c | Sistem mendukung adaptive threshold berbasis mean brightness frame | Opsional |
| FR-08 | Threshold dapat di-tuning per slot (opsional, default global) | Opsional |

### 1.3 Manajemen Slot (Polygon)

| Kode | Requirement | Prioritas |
|---|---|---|
| FR-09 | Admin dapat menambah polygon slot dengan double-click di window picker | Wajib |
| FR-10 | Admin dapat menggeser titik polygon untuk resize | Wajib |
| FR-11 | Admin dapat menggeser badan polygon untuk pindah lokasi | Wajib |
| FR-12 | Admin dapat menghapus polygon dengan right-click | Wajib |
| FR-13 | Polygon tersimpan di tabel `slots` (SQLite, bukan file pickle) | Wajib |
| FR-14 | Polygon dimuat ulang otomatis saat detection engine start (cache dengan TTL 5 detik) | Wajib |

### 1.4 Penyimpanan Data

| Kode | Requirement | Prioritas |
|---|---|---|
| FR-15 | Status terkini tiap slot disimpan di tabel `slot_status` | Wajib |
| FR-16 | Setiap perubahan status (FREE↔FULL) tercatat di tabel `occupancy_log` | Wajib |
| FR-17 | Sistem menyimpan snapshot agregat (total/free/full) tiap N detik di `occupancy_summary` | Wajib |
| FR-18 | Event sistem (RTSP putus, reconnect) tercatat di `system_event` | Opsional |

### 1.5 Backend API

| Kode | Requirement | Prioritas |
|---|---|---|
| FR-19 | `GET /video_feed` mengembalikan MJPEG stream live | Wajib |
| FR-20 | `GET /api/slots` mengembalikan daftar slot + status terkini | Wajib |
| FR-21 | `GET /api/slots/{id}` mengembalikan detail satu slot | Wajib |
| FR-22 | `POST /api/slots` membuat slot baru (polygon + kode) | Wajib |
| FR-23 | `PUT /api/slots/{id}` mengubah polygon slot | Wajib |
| FR-24 | `DELETE /api/slots/{id}` menghapus slot | Wajib |
| FR-25 | `GET /api/history` mengembalikan log historis dengan filter waktu | Wajib |
| FR-26 | `GET /api/summary` mengembalikan agregat per jam / per hari | Wajib |
| FR-27 | `WS /ws/slots` mem-broadcast perubahan status secara realtime | Wajib |
| FR-28 | API menyediakan dokumentasi otomatis di `/docs` (Swagger UI) | Wajib |

### 1.6 Web Dashboard

| Kode | Requirement | Prioritas |
|---|---|---|
| FR-29 | Dashboard menampilkan live video stream dengan overlay polygon + status | Wajib |
| FR-30 | Dashboard menampilkan counter `Free / Total` besar di atas | Wajib |
| FR-31 | Dashboard menampilkan grid kartu per slot (warna hijau/merah) | Wajib |
| FR-32 | Dashboard menampilkan chart historis okupansi (Chart.js) | Wajib |
| FR-33 | Dashboard menerima update via WebSocket tanpa reload | Wajib |
| FR-34 | Dashboard responsive di layar HP (mobile-first via Tailwind) | Wajib |
| FR-35 | Halaman admin (opsional) menampilkan daftar slot + tombol delete/edit | Opsional |
| FR-35a | Dashboard menampilkan tombol override per slot (Bebas/Penuh/Auto) | Wajib |

### 1.7 Konfigurasi

| Kode | Requirement | Prioritas |
|---|---|---|
| FR-36 | Semua kredensial (RTSP, MySQL) berasal dari file `.env` | Wajib |
| FR-37 | Threshold deteksi, resolusi, interval, port API dapat diubah via `.env` tanpa edit kode | Wajib |
| FR-38 | File `.env.example` disertakan di repo, file `.env` di-gitignore | Wajib |

---

## 2. Non-Functional Requirements (NFR)

### 2.1 Performance

| Kode | Requirement | Target |
|---|---|---|
| NFR-01 | Frame rate proses | ≥ 10 FPS pada 1280×720 |
| NFR-02 | Latency status berubah → tampil di dashboard | < 1 detik |
| NFR-03 | Waktu respons REST API | < 200 ms (p95) |
| NFR-04 | Konsumsi RAM | < 1 GB |

### 2.2 Reliability

| Kode | Requirement | Target |
|---|---|---|
| NFR-05 | Auto-reconnect bila RTSP putus | Maksimal 5 detik |
| NFR-06 | Sistem berjalan stabil minimal 30 menit non-stop tanpa crash | Wajib |
| NFR-07 | Logging error ke file & stdout | Wajib |

### 2.3 Akurasi

| Kode | Requirement | Target |
|---|---|---|
| NFR-08 | Akurasi deteksi pada pencahayaan normal (siang) | ≥ 90% |
| NFR-09 | Akurasi pada pencahayaan rendah (malam) | ≥ 75% (best effort) |
| NFR-10 | False Positive rate | < 10% |

### 2.4 Usability

| Kode | Requirement | Target |
|---|---|---|
| NFR-11 | Dashboard berjalan di Chrome/Edge/Firefox versi terbaru | Wajib |
| NFR-12 | Dashboard responsive di layar 360px ke atas | Wajib |
| NFR-13 | Setup awal (install + first run) | < 30 menit oleh orang teknis |

### 2.5 Maintainability

| Kode | Requirement | Target |
|---|---|---|
| NFR-14 | Modul `core/` (preprocessor, detector, geometry) bebas dari dependency I/O (testable) | Wajib |
| NFR-15 | Coverage unit test untuk modul `core/` | ≥ 60% |
| NFR-16 | Mengikuti PEP 8 (cek dengan `ruff`) | Wajib |

### 2.6 Security

| Kode | Requirement | Target |
|---|---|---|
| NFR-17 | Tidak ada kredensial hardcoded di source | Wajib |
| NFR-18 | `.env` masuk `.gitignore` | Wajib |
| NFR-19 | API binding `0.0.0.0` hanya untuk LAN, dokumentasikan risikonya | Wajib |

### 2.7 Portability

| Kode | Requirement | Target |
|---|---|---|
| NFR-20 | Berjalan di Windows 10/11 dan Ubuntu 22.04 | Wajib |
| NFR-21 | Tidak bergantung pada path absolut spesifik OS | Wajib |

---

## 3. Hardware Requirement

| Komponen | Minimum | Rekomendasi |
|---|---|---|
| CPU | Intel i3 gen 8 / Ryzen 3 | Intel i5 gen 10+ / Ryzen 5 |
| RAM | 4 GB | 8 GB |
| Storage | 20 GB free | 50 GB free |
| GPU | Tidak wajib | — |
| Network | Wi-Fi/LAN sama dengan CCTV | Kabel LAN |
| CCTV | RTSP H.264, 720p+ | Dahua dengan substream |

---

## 4. Software Requirement

### 4.1 System
| Software | Versi |
|---|---|
| Python | 3.10 / 3.11 (rekomendasi) |
| MySQL Server | 8.0 |
| Git | latest |
| Browser modern | Chrome / Edge / Firefox |

### 4.2 Python Dependencies (`requirements.txt`)

```
opencv-python>=4.10.0
numpy>=1.26.4

fastapi>=0.115.0
uvicorn[standard]>=0.32.0

sqlalchemy>=2.0.36

python-dotenv>=1.0.1
pydantic-settings>=2.6.1

websockets>=13.1

pytest>=8.3.3
pytest-asyncio>=0.24.0
```

### 4.3 Frontend (CDN, no build)
- Tailwind CSS 3 (CDN)
- Chart.js 4 (CDN)
- Vanilla JavaScript ES6+

---

## 5. Constraint

- Tidak menggunakan deep learning (YOLO/dll) — fokus image processing klasik.
- Tidak menggunakan deployment cloud — semua di satu PC lokal.
- Tidak ada autentikasi user di iterasi pertama (bisa ditambah nanti).
- Database SQLite (tidak perlu MySQL server).
