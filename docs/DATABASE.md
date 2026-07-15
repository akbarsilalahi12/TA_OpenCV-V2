# DATABASE

Skema database SQLite untuk sistem deteksi slot parkir.

---

## 1. Ringkasan

| Item | Nilai |
|---|---|
| RDBMS | SQLite 3 (built-in Python) |
| Database file | `parking.db` (auto-generated) |
| Driver Python | sqlite3 (stdlib) |
| ORM | SQLAlchemy 2.x |
| No setup required | Database dibuat otomatis saat pertama kali `run_server.py` dijalankan |

---

## 2. Daftar Tabel

| Tabel | Fungsi |
|---|---|
| `slots` | Master polygon slot parkir |
| `slot_status` | Status terkini tiap slot (1 row per slot) |
| `occupancy_log` | Log historis tiap kali status berubah |
| `occupancy_summary` | Snapshot agregat per N detik untuk chart dashboard |
| `system_event` | Audit event sistem (RTSP putus, reconnect, dll) |

---

## 3. ERD (Entity Relationship Diagram)

```
┌───────────────────────┐
│ slots                 │
│ ─────────────────     │
│ PK id                 │
│    slot_code (UQ)     │
│    polygon_json       │
│    is_active          │
│    created_at         │
│    updated_at         │
└──────────┬────────────┘
           │ 1
           │
       ┌───┴────┐
       │        │
       │ 1      │ N
       ▼        ▼
┌──────────────┐  ┌─────────────────────┐
│ slot_status  │  │ occupancy_log       │
│ ──────────── │  │ ─────────────────── │
│ PK slot_id   │  │ PK id               │
│    status    │  │ FK slot_id          │
│    ratio     │  │    status           │
│    updated_at│  │    ratio            │
└──────────────┘  │    detected_at      │
                  └─────────────────────┘

┌──────────────────────┐    ┌──────────────────┐
│ occupancy_summary    │    │ system_event     │
│ ──────────────────── │    │ ──────────────── │
│ PK id                │    │ PK id            │
│    snapshot_at       │    │    event_type    │
│    total_slot        │    │    message       │
│    free_slot         │    │    created_at    │
│    full_slot         │    └──────────────────┘
└──────────────────────┘
```

Relasi:
- `slots` 1 — 1 `slot_status` (tiap slot punya satu baris status terkini)
- `slots` 1 — N `occupancy_log` (tiap slot punya banyak log perubahan)
- `occupancy_summary` standalone (agregat sistem)
- `system_event` standalone (event sistem)

---

## 4. DDL (SQLAlchemy ORM)

Tabel dibuat otomatis oleh `init_db()` saat server start. Tidak perlu menjalankan DDL manual. Berikut mapping ORM-nya:

```python
class Slot(Base):
    __tablename__ = "slots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    slot_code = Column(String(20), unique=True, nullable=False)
    polygon_json = Column(JSON, nullable=False)
    is_active = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    updated_at = Column(DateTime, server_default=func.current_timestamp(),
                        server_onupdate=func.current_timestamp())

class SlotStatus(Base):
    __tablename__ = "slot_status"
    slot_id = Column(Integer, ForeignKey("slots.id", ondelete="CASCADE"), primary_key=True)
    status = Column(Enum("FREE", "FULL"), nullable=False)
    ratio = Column(Numeric(5, 3), nullable=True)
    updated_at = Column(DateTime, server_default=func.current_timestamp(),
                        server_onupdate=func.current_timestamp())

class OccupancyLog(Base):
    __tablename__ = "occupancy_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    slot_id = Column(Integer, ForeignKey("slots.id", ondelete="CASCADE"), nullable=False)
    status = Column(Enum("FREE", "FULL"), nullable=False)
    ratio = Column(Numeric(5, 3), nullable=True)
    detected_at = Column(DateTime, server_default=func.current_timestamp())

class OccupancySummary(Base):
    __tablename__ = "occupancy_summary"
    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_at = Column(DateTime, nullable=False)
    total_slot = Column(Integer, nullable=False)
    free_slot = Column(Integer, nullable=False)
    full_slot = Column(Integer, nullable=False)

class SystemEvent(Base):
    __tablename__ = "system_event"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(40), nullable=False)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())
```

---

## 5. Penjelasan Tabel

### 5.1 `slots`
Master polygon slot parkir, menggantikan file pickle `carParkPos`.

| Kolom | Tipe | Catatan |
|---|---|---|
| `id` | INTEGER PK | Auto increment |
| `slot_code` | VARCHAR(20) UNIQUE | Kode label, mis. `A1`, `A2`, `S001`. Auto-generate saat picker tambah polygon |
| `polygon_json` | JSON (text) | Format `[[x,y],[x,y],[x,y],[x,y]]` |
| `is_active` | INTEGER | Soft delete: `0` = nonaktif, `1` = aktif |
| `created_at` / `updated_at` | DATETIME | Audit timestamp |

Contoh isi `polygon_json`:
```json
[[120, 200], [240, 200], [240, 260], [120, 260]]
```

### 5.2 `slot_status`
Selalu tepat 1 row per slot. Di-upsert oleh detection loop dengan SQLite `INSERT ... ON CONFLICT`.

| Kolom | Tipe | Catatan |
|---|---|---|
| `slot_id` | INTEGER PK FK | Sekaligus FK ke `slots.id` |
| `status` | TEXT CHECK | `FREE` atau `FULL` (via Enum) |
| `ratio` | NUMERIC(5,3) | Rasio piksel non-zero (0.000 – 1.000) untuk debugging |
| `updated_at` | DATETIME | Auto update |

### 5.3 `occupancy_log`
Insert **hanya saat status berubah** (FREE→FULL atau sebaliknya). Bukan tiap frame, supaya tabel tidak meledak.

Estimasi volume: 50 slot × 20 perubahan/hari = ~1000 row/hari → ringan.

### 5.4 `occupancy_summary`
Insert tiap interval (default 60 detik) dari detection loop. Dipakai oleh Chart.js di dashboard.

Estimasi: 1440 row/hari (per menit) → ringan, mudah di-query untuk grafik.

### 5.5 `system_event`
Catatan event sistem untuk audit. Contoh `event_type`:
- `RTSP_DISCONNECT`
- `RTSP_RECONNECT`
- `DB_ERROR`
- `STARTUP`
- `SHUTDOWN`

---

## 6. Setup Database

Database **tidak perlu setup manual**. SQLite `parking.db` dibuat otomatis saat pertama kali menjalankan server:

```bash
python run_server.py
```

File database akan muncul di root proyek (`parking.db`). Untuk reset, cukup hapus file tersebut.

Update `.env` bila ingin lokasi kustom:
```env
DATABASE_URL=sqlite:///parking.db
```

---

## 7. Query Contoh untuk Dashboard & Laporan

### 7.1 Status semua slot terkini
```sql
SELECT s.id, s.slot_code, ss.status, ss.ratio, ss.updated_at
FROM slots s
LEFT JOIN slot_status ss ON ss.slot_id = s.id
WHERE s.is_active = 1
ORDER BY s.slot_code;
```

### 7.2 Hitung free vs full saat ini
```sql
SELECT
    SUM(ss.status = 'FREE') AS free_slot,
    SUM(ss.status = 'FULL') AS full_slot,
    COUNT(*)                AS total_slot
FROM slots s
JOIN slot_status ss ON ss.slot_id = s.id
WHERE s.is_active = 1;
```

### 7.3 Grafik okupansi 24 jam terakhir (per jam)
```sql
SELECT
    DATE_FORMAT(snapshot_at, '%Y-%m-%d %H:00') AS hour_bucket,
    AVG(full_slot) AS avg_full,
    AVG(free_slot) AS avg_free
FROM occupancy_summary
WHERE snapshot_at >= NOW() - INTERVAL 24 HOUR
GROUP BY hour_bucket
ORDER BY hour_bucket;
```

### 7.4 Slot paling sering terisi (jam tersibuk)
```sql
SELECT
    s.slot_code,
    SUM(ol.status = 'FULL') AS full_count
FROM occupancy_log ol
JOIN slots s ON s.id = ol.slot_id
WHERE ol.detected_at >= NOW() - INTERVAL 7 DAY
GROUP BY s.slot_code
ORDER BY full_count DESC;
```

### 7.5 Durasi rata-rata terisi per slot (lebih advance)
```sql
SELECT
    slot_id,
    AVG(TIMESTAMPDIFF(SECOND, prev_time, detected_at)) AS avg_duration_sec
FROM (
    SELECT
        slot_id,
        status,
        detected_at,
        LAG(detected_at) OVER (PARTITION BY slot_id ORDER BY detected_at) AS prev_time,
        LAG(status)      OVER (PARTITION BY slot_id ORDER BY detected_at) AS prev_status
    FROM occupancy_log
) t
WHERE prev_status = 'FULL' AND status = 'FREE'
GROUP BY slot_id;
```

---

## 8. Migrasi dari File Pickle ke SQLite

Script one-shot di `app/tools/migrate_pickle_to_mysql.py`:

```bash
python -m app.tools.migrate_pickle_to_mysql CarParkPos
```

Setelah migrasi sukses, file pickle bisa diarsipkan/hapus.

---

## 9. Backup & Restore

Cukup copy file `parking.db`:

```bash
# Backup
copy parking.db parking.db.backup

# Restore
copy parking.db.backup parking.db
```

---

## 10. Estimasi Storage

| Tabel | Estimasi/hari | 1 bulan | 1 tahun |
|---|---|---|---|
| `slots` | ~50 row total (statis) | sama | sama |
| `slot_status` | 50 row (di-update) | sama | sama |
| `occupancy_log` | ~1.000 row | ~30 K | ~365 K |
| `occupancy_summary` | 1.440 row | ~43 K | ~525 K |
| `system_event` | < 100 row | ~3 K | ~36 K |

Total < 100 MB/tahun → sangat ringan.
