# Dokumentasi Tugas Akhir — Sistem Deteksi Slot Parkir berbasis OpenCV

Index dokumentasi proyek. Mulai dari [`PLANNING.md`](PLANNING.md) untuk overview, lalu lanjut sesuai kebutuhan.

---

## Daftar Dokumen

| # | File | Deskripsi |
|---|---|---|
| 1 | [PLANNING.md](PLANNING.md) | **Mulai dari sini.** Latar belakang, tujuan, ruang lingkup, deliverables, stack, keputusan desain, risiko, kriteria sukses |
| 2 | [REQUIREMENTS.md](REQUIREMENTS.md) | Functional requirement (FR-01..38) + Non-functional requirement (NFR-01..21) + hardware/software requirement |
| 3 | [ARCHITECTURE.md](ARCHITECTURE.md) | Block diagram, layered architecture, breakdown modul, sequence diagram, threading, data flow, flowchart algoritma |
| 4 | [DATABASE.md](DATABASE.md) | Skema SQLite, ERD, ORM models, contoh query untuk dashboard & laporan, migrasi pickle → DB |
| 5 | [API.md](API.md) | Spesifikasi REST API + WebSocket, contoh request/response, Pydantic schema, contoh pemakaian cURL & JS |
| 6 | [ROADMAP.md](ROADMAP.md) | Timeline 9 fase pengerjaan, ~10 hari kerja, dependency, milestone demo |
| 7 | [FOLDER_STRUCTURE.md](FOLDER_STRUCTURE.md) | Struktur folder target, naming convention, mapping file lama → baru, aturan import |

## Dokumen yang akan dibuat saat implementasi

| File | Dibuat di Fase |
|---|---|
| `INSTALL.md` | Fase 8 (Dokumentasi) |
| `USER_MANUAL.md` | Fase 8 (Dokumentasi) |
| `TESTING.md` | Fase 7 (Testing & Tuning) |
| `diagrams/*.png` | Fase 8 (export draw.io / Mermaid) |

---

## Urutan Membaca

**Untuk Anda (developer):**
1. `PLANNING.md` — pahami big picture
2. `ROADMAP.md` — pahami urutan kerja
3. `FOLDER_STRUCTURE.md` — pahami target struktur
4. `ARCHITECTURE.md` + `DATABASE.md` + `API.md` — referensi teknis saat coding

**Untuk dosen pembimbing / penguji:**
1. `PLANNING.md` — overview & justifikasi keputusan
2. `REQUIREMENTS.md` — apa yang dibangun
3. `ARCHITECTURE.md` — bagaimana dibangun
4. `TESTING.md` (akan ada) — bukti kerja sistem
