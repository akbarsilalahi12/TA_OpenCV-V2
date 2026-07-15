# PLANNING — Sistem Deteksi Slot Parkir berbasis OpenCV

> Dokumen induk perencanaan Tugas Akhir.  
> Sistem mendeteksi status slot parkir (FREE/FULL) secara real-time dari CCTV RTSP, menyimpan ke MySQL, dan menampilkan di web dashboard yang dapat diakses dari perangkat lain di jaringan LAN yang sama.

---

## 1. Latar Belakang

Saat ini terdapat prototipe deteksi parkir berbasis OpenCV (`main.py`, `ParkingSpacePicker.py`) yang outputnya hanya berupa window OpenCV lokal (`cv2.imshow`). Output ini belum cukup sebagai produk akhir Tugas Akhir karena:

- Tidak ada penyimpanan historis (tidak bisa dibuat laporan).
- Tidak bisa diakses dari perangkat lain (HP, laptop pengunjung).
- Konfigurasi (RTSP, threshold) hardcoded.
- Tidak ada API untuk integrasi.
- Tidak ada dokumentasi formal.

## 2. Tujuan

Membangun **sistem terintegrasi lokal** yang terdiri dari:

1. **Detection Engine** — pipeline OpenCV (refactor dari kode existing).
2. **Backend API** — FastAPI (REST + WebSocket + MJPEG).
3. **Database** — MySQL 8 untuk slot, status, log historis.
4. **Web Dashboard** — live video, counter, grid status, chart historis.
5. **Tool Kalibrasi Polygon** — desktop tool (refactor `ParkingSpacePicker.py`).
6. **Dokumentasi** — teknis (README/INSTALL/API/dst.) + akademis (laporan TA).

## 3. Ruang Lingkup

- **Deployment:** 100% lokal di satu PC/laptop yang berada di LAN yang sama dengan CCTV.
- **Akses:** dashboard dapat dibuka dari HP/laptop lain di Wi-Fi yang sama via IP lokal PC server (mis. `http://192.168.18.50:8000`).
- **Tidak termasuk:** deployment cloud, autentikasi user, mobile app native, plat nomor (ANPR).

## 4. Asumsi & Batasan

| | Detail |
|---|---|
| CCTV | Dahua, RTSP H.264 |
| Resolusi proses | 1280×720 |
| Metode | Image processing klasik (grayscale → blur → threshold → morfologi → polygon ratio) |
| Akurasi target | ≥ 90% pada kondisi pencahayaan normal (siang) |
| Frame rate target | ≥ 10 FPS |
| OS target | Windows 10/11 (utama), Ubuntu 22.04 (kompatibel) |

## 5. Stakeholder

| Peran | Kepentingan |
|---|---|
| Mahasiswa (Anda) | Penyusun & developer sistem, presenter sidang TA |
| Dosen pembimbing | Reviewer arsitektur & metodologi |
| Penguji sidang | Reviewer akhir, melihat demo & dokumentasi |
| Admin parkir (skenario) | Memantau & mengkalibrasi sistem |
| Pengunjung (skenario) | Melihat info slot kosong dari HP |

## 6. Output / Deliverables

### 6.1 Software
- Source code lengkap di repo Git
- File `requirements.txt`, `.env.example`, `schema.sql`
- Web dashboard siap pakai
- Tool kalibrasi polygon
- Database MySQL terisi data demo

### 6.2 Dokumentasi Teknis (`docs/`)
| File | Fungsi |
|---|---|
| `PLANNING.md` | Dokumen ini — perencanaan menyeluruh |
| `REQUIREMENTS.md` | Functional & non-functional requirement |
| `ARCHITECTURE.md` | Arsitektur sistem & modul |
| `DATABASE.md` | Skema MySQL + ERD |
| `API.md` | Spesifikasi REST + WebSocket |
| `ROADMAP.md` | Timeline pengerjaan |
| `FOLDER_STRUCTURE.md` | Struktur folder target |
| `INSTALL.md` | Panduan instalasi (akan dibuat saat implementasi) |
| `USER_MANUAL.md` | Panduan pemakaian (akan dibuat saat implementasi) |

### 6.3 Dokumentasi Akademis (Laporan TA)
- BAB I Pendahuluan
- BAB II Tinjauan Pustaka (OpenCV, image processing, RTSP, polygon ROI)
- BAB III Metodologi (block diagram, flowchart algoritma, perancangan UI & DB)
- BAB IV Implementasi & Pengujian (akurasi, latency, kondisi pencahayaan)
- BAB V Penutup
- Lampiran: source code, ERD, screenshot

### 6.4 Diagram Wajib
- Block diagram sistem
- Flowchart algoritma deteksi
- Use case diagram
- ERD database
- Sequence diagram (request video, request status)

## 7. Stack Teknologi (Final)

| Lapisan | Pilihan | Alasan |
|---|---|---|
| Bahasa utama | **Python 3.11** | Ekosistem CV terbaik |
| Computer Vision | **OpenCV 4.10** | Sudah dipakai, ringan |
| Backend | **FastAPI 0.115** | Async native, auto Swagger UI |
| ASGI server | **Uvicorn** | Standar FastAPI |
| Database | **SQLite 3** (built-in) | Zero setup, file-based, cukup untuk single-PC |
| ORM | **SQLAlchemy 2.x** | Mature, type-safe |
| Realtime | **WebSocket** (built-in FastAPI) | Push status ke browser |
| Streaming video | **MJPEG over HTTP** | Simpel, langsung jalan di `<img>` |
| Frontend | **Vanilla JS + Tailwind CDN + Chart.js** | No build tool, cepat |
| Testing | **pytest** | Standar Python |
| Diagram | **draw.io / Mermaid** | Open, mudah edit |

## 8. Keputusan Desain

| Topik | Keputusan | Catatan |
|---|---|---|
| Deployment | Lokal (single PC) | Akses LAN |
| Database | SQLite | Zero setup, file-based, auto-create |
| Frontend | Vanilla JS + Tailwind CDN | Tidak butuh Node.js |
| Picker polygon | Desktop window (refactor existing) | Cepat, sudah ada base-nya |
| Metode deteksi | OpenCV klasik (no ML) | YOLOv8 opsional di iterasi berikutnya |
| Streaming | MJPEG | Hindari kompleksitas WebRTC |
| Konfigurasi | `.env` via `pydantic-settings` | Kredensial keluar dari source |

## 9. Risiko & Mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| RTSP putus | Detection mati | Auto-reconnect di `rtsp_reader.py` |
| Threshold tidak optimal di malam hari | Akurasi turun | Konfigurabel via `.env`; uji multi-kondisi |
| MySQL tidak jalan | Sistem error | Health-check di startup + log error jelas |
| FPS rendah | UI lag | Resize ke 1280×720, deteksi tiap N ms (tidak tiap frame) |
| Polygon mismatch resolusi | Slot salah posisi | Lock resolusi proses di `.env` (`FRAME_WIDTH/HEIGHT`) |
| Kredensial bocor di Git | Security | `.env` di-`.gitignore`, hanya commit `.env.example` |

## 10. Kriteria Sukses (Definition of Done)

Sistem dianggap selesai bila:

- [ ] Detection engine berjalan stabil ≥ 30 menit non-stop tanpa crash
- [ ] Auto-reconnect RTSP terbukti (uji cabut & sambung kabel)
- [ ] Akurasi deteksi ≥ 90% pada 30+ sampel uji
- [ ] FPS ≥ 10 pada 1280×720
- [ ] Dashboard menampilkan live video + counter + grid + chart
- [ ] Status berubah di dashboard < 1 detik setelah perubahan riil
- [ ] Dashboard bisa dibuka dari HP di Wi-Fi yang sama
- [ ] Polygon tersimpan di SQLite (bukan pickle lagi)
- [ ] Semua file dokumentasi di `docs/` lengkap
- [ ] Diagram (block, flowchart, ERD, use case) tersedia
- [ ] Repo Git bersih, `.env` tidak ter-commit, ada `README.md`

## 11. Referensi Dokumen Lain

- [REQUIREMENTS.md](REQUIREMENTS.md) — daftar requirement detail
- [ARCHITECTURE.md](ARCHITECTURE.md) — diagram & breakdown modul
- [DATABASE.md](DATABASE.md) — skema MySQL
- [API.md](API.md) — spesifikasi endpoint
- [ROADMAP.md](ROADMAP.md) — timeline pengerjaan
- [FOLDER_STRUCTURE.md](FOLDER_STRUCTURE.md) — struktur folder target
