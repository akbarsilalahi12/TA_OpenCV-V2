# DATABASE

Skema database MySQL untuk sistem deteksi slot parkir.

---

## 1. Ringkasan

| Item | Nilai |
|---|---|
| RDBMS | MySQL 8.0 (atau MariaDB 10.6+) |
| Database name | `parking_db` |
| Charset | `utf8mb4` |
| Collation | `utf8mb4_unicode_ci` |
| Engine tabel | InnoDB |
| Driver Python | PyMySQL + cryptography |
| ORM | SQLAlchemy 2.x |

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
   (standalone)              (standalone)
```

Relasi:
- `slots` 1 — 1 `slot_status` (tiap slot punya satu baris status terkini)
- `slots` 1 — N `occupancy_log` (tiap slot punya banyak log perubahan)
- `occupancy_summary` standalone (agregat sistem)
- `system_event` standalone (event sistem)

---

## 4. DDL Lengkap (`schema.sql`)

```sql
-- =========================================================
-- Database
-- =========================================================
CREATE DATABASE IF NOT EXISTS parking_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE parking_db;

-- =========================================================
-- Tabel: slots
-- Master polygon slot parkir
-- =========================================================
CREATE TABLE IF NOT EXISTS slots (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    slot_code     VARCHAR(20)  NOT NULL UNIQUE,
    polygon_json  JSON         NOT NULL,
    is_active     TINYINT(1)   NOT NULL DEFAULT 1,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =========================================================
-- Tabel: slot_status
-- Status terkini tiap slot (di-upsert tiap deteksi)
-- =========================================================
CREATE TABLE IF NOT EXISTS slot_status (
    slot_id     INT PRIMARY KEY,
    status      ENUM('FREE','FULL') NOT NULL,
    ratio       DECIMAL(5,3) NULL,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                          ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_status_slot
        FOREIGN KEY (slot_id) REFERENCES slots(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =========================================================
-- Tabel: occupancy_log
-- Log historis perubahan status (insert hanya saat status BERUBAH)
-- =========================================================
CREATE TABLE IF NOT EXISTS occupancy_log (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    slot_id       INT NOT NULL,
    status        ENUM('FREE','FULL') NOT NULL,
    ratio         DECIMAL(5,3) NULL,
    detected_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_slot_time (slot_id, detected_at),
    INDEX idx_time (detected_at),
    CONSTRAINT fk_log_slot
        FOREIGN KEY (slot_id) REFERENCES slots(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =========================================================
-- Tabel: occupancy_summary
-- Snapshot agregat (insert tiap N detik / N menit)
-- =========================================================
CREATE TABLE IF NOT EXISTS occupancy_summary (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    snapshot_at  DATETIME NOT NULL,
    total_slot   INT NOT NULL,
    free_slot    INT NOT NULL,
    full_slot    INT NOT NULL,
    INDEX idx_time (snapshot_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =========================================================
-- Tabel: system_event
-- Audit event sistem (opsional)
-- =========================================================
CREATE TABLE IF NOT EXISTS system_event (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    event_type  VARCHAR(40) NOT NULL,
    message     TEXT,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_type_time (event_type, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 5. Penjelasan Tabel

### 5.1 `slots`
Master polygon slot parkir, menggantikan file pickle `carParkPos`.

| Kolom | Tipe | Catatan |
|---|---|---|
| `id` | INT PK | Auto increment |
| `slot_code` | VARCHAR(20) UNIQUE | Kode label, mis. `A1`, `A2`, `B1`. Auto-generate saat picker tambah polygon |
| `polygon_json` | JSON | Format `[[x,y],[x,y],[x,y],[x,y]]` (4 titik) |
| `is_active` | TINYINT(1) | Soft delete: `0` = nonaktif, `1` = aktif |
| `created_at` / `updated_at` | DATETIME | Audit timestamp |

Contoh isi `polygon_json`:
```json
[[120, 200], [240, 200], [240, 260], [120, 260]]
```

### 5.2 `slot_status`
Selalu tepat 1 row per slot. Di-upsert oleh detection loop.

| Kolom | Tipe | Catatan |
|---|---|---|
| `slot_id` | INT PK FK | Sekaligus FK ke `slots.id` |
| `status` | ENUM | `FREE` atau `FULL` |
| `ratio` | DECIMAL(5,3) | Rasio piksel non-zero (0.000 – 1.000) untuk debugging |
| `updated_at` | DATETIME | Auto update |

### 5.3 `occupancy_log`
Insert **hanya saat status berubah** (FREE→FULL atau sebaliknya). Bukan tiap frame, supaya tabel tidak meledak.

Estimasi volume: 50 slot × 20 perubahan/hari = ~1000 row/hari → ringan.

### 5.4 `occupancy_summary`
Insert tiap interval (mis. 60 detik) dari detection loop. Dipakai oleh Chart.js di dashboard.

Estimasi: 1440 row/hari (per menit) → ringan, mudah di-query untuk grafik.

### 5.5 `system_event`
Catatan event sistem untuk audit. Contoh `event_type`:
- `RTSP_DISCONNECT`
- `RTSP_RECONNECT`
- `DB_ERROR`
- `STARTUP`
- `SHUTDOWN`

---

## 6. Setup Database (Langkah)

```sql
-- 1. Login MySQL sebagai root
--    mysql -u root -p

-- 2. Jalankan schema
SOURCE app/db/schema.sql;

-- 3. Buat user khusus aplikasi (jangan pakai root!)
CREATE USER 'parking_user'@'localhost' IDENTIFIED BY 'parking_pass';

GRANT SELECT, INSERT, UPDATE, DELETE
  ON parking_db.*
  TO 'parking_user'@'localhost';

FLUSH PRIVILEGES;

-- 4. Verifikasi
SHOW DATABASES;
USE parking_db;
SHOW TABLES;
```

Update `.env`:
```env
MYSQL_USER=parking_user
MYSQL_PASSWORD=parking_pass
MYSQL_DATABASE=parking_db
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

## 8. Migrasi dari File Pickle ke MySQL

Script one-shot di `app/tools/migrate_pickle_to_mysql.py`:

```python
import pickle, json
from app.db.connection import SessionLocal
from app.db.models import Slot

with open("CarParkPos", "rb") as f:
    pos_list = pickle.load(f)

session = SessionLocal()
for i, polygon in enumerate(pos_list, start=1):
    slot = Slot(
        slot_code=f"S{i:03d}",
        polygon_json=json.dumps(polygon),
        is_active=1,
    )
    session.add(slot)

session.commit()
session.close()
print(f"Migrated {len(pos_list)} slots")
```

Setelah migrasi sukses, file pickle bisa diarsipkan/hapus.

---

## 9. Backup & Restore

```bash
# Backup
mysqldump -u root -p parking_db > parking_db_backup.sql

# Restore
mysql -u root -p parking_db < parking_db_backup.sql
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
