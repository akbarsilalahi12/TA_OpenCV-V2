# INSTALL — Panduan Instalasi

Panduan setup sistem dari nol di Windows 10/11 (atau Ubuntu 22.04).

---

## 1. Prasyarat

| Software | Versi | Cara install |
|---|---|---|
| Python | 3.10 / 3.11 | https://www.python.org/downloads/ |
| MySQL Server | 8.0 | https://dev.mysql.com/downloads/installer/ atau XAMPP |
| Git | latest | https://git-scm.com/ |
| (opsional) MySQL Workbench | latest | untuk demo data |

> Saat install Python, centang **"Add Python to PATH"**.

---

## 2. Clone Repo

```bash
git clone https://github.com/sahabiard/TA_OpenCV.git
cd TA_OpenCV
```

---

## 3. Virtual Environment + Dependency

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

Verifikasi:
```bash
python -c "import cv2, fastapi, sqlalchemy, pymysql; print('OK')"
```

---

## 4. Setup MySQL

Login MySQL sebagai root:

```bash
mysql -u root -p
```

Lalu jalankan:

```sql
SOURCE app/db/schema.sql;

CREATE USER IF NOT EXISTS 'parking_user'@'localhost' IDENTIFIED BY 'parking_pass';
GRANT SELECT, INSERT, UPDATE, DELETE ON parking_db.* TO 'parking_user'@'localhost';
FLUSH PRIVILEGES;

USE parking_db;
SHOW TABLES;
```

Output yang diharapkan:
```
+----------------------+
| Tables_in_parking_db |
+----------------------+
| occupancy_log        |
| occupancy_summary    |
| slot_status          |
| slots                |
| system_event         |
+----------------------+
```

---

## 5. Konfigurasi `.env`

```bash
# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```

Edit `.env` sesuai konfigurasi lokal:

```env
RTSP_URL=rtsp://admin:PASSWORD_ANDA@IP_CCTV:554/cam/realmonitor?channel=1&subtype=0

MYSQL_HOST=localhost
MYSQL_USER=parking_user
MYSQL_PASSWORD=parking_pass
MYSQL_DATABASE=parking_db

DETECTION_THRESHOLD=0.18
API_HOST=0.0.0.0
API_PORT=8000
```

---

## 6. Verifikasi RTSP

```bash
python rtsp_check.py "rtsp://admin:PASSWORD@IP:554/cam/realmonitor?channel=1&subtype=0"
```

Harus output:
```
isOpened True
```

---

## 7. (Opsional) Migrasi Polygon Lama

Jika sudah punya file `CarParkPos` (pickle) dari prototipe lama:

```bash
python -m app.tools.migrate_pickle_to_mysql CarParkPos
```

---

## 8. Kalibrasi Polygon (Buat Slot)

Jalankan tool desktop:

```bash
python run_picker.py
```

Kontrol:
- **Double click** : tambah polygon
- **Drag titik**   : resize
- **Drag badan**   : pindah
- **Right click**  : hapus
- **R**            : reload dari DB
- **Q / Esc**      : keluar

Setiap perubahan otomatis tersimpan ke MySQL.

---

## 9. Jalankan Server

```bash
python run_server.py
```

Output yang diharapkan:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

---

## 10. Akses Dashboard

Dari PC server:
```
http://localhost:8000
```

Dari HP/laptop di Wi-Fi yang sama (cari IP PC dengan `ipconfig` di Windows atau `ip addr` di Linux):
```
http://192.168.x.x:8000
```

API docs (Swagger UI):
```
http://localhost:8000/docs
```

---

## 11. Verifikasi Test

```bash
pytest
```

Output:
```
================ test session starts ================
collected 16 items

tests/test_detector.py ......                  [ 37%]
tests/test_geometry.py .....                    [ 68%]
tests/test_preprocessor.py .....                [100%]
================ 16 passed in 1.2s ==================
```

---

## 12. Troubleshoot

### MySQL connection refused
- Pastikan MySQL service jalan: `services.msc` (Windows) atau `systemctl status mysql` (Linux)
- Cek port 3306 tidak diblok firewall

### `ModuleNotFoundError: No module named 'cv2'`
- Aktifkan venv dulu: `venv\Scripts\activate`
- `pip install -r requirements.txt`

### RTSP tidak konek
- Cek dari PC server: ping IP CCTV
- Coba URL di VLC dulu untuk validasi
- Pastikan PC server di LAN yang sama dengan CCTV

### Dashboard tidak bisa diakses dari HP
- Pastikan `API_HOST=0.0.0.0` di `.env`
- Buka port 8000 di Windows Firewall:
  ```
  netsh advfirewall firewall add rule name="Parking 8000" dir=in action=allow protocol=TCP localport=8000
  ```

### FPS rendah
- Turunkan resolusi di `.env`: `FRAME_WIDTH=960`, `FRAME_HEIGHT=540`
- Naikkan `DETECT_INTERVAL_MS=300`

### Status semua FULL atau semua FREE
- Tuning `DETECTION_THRESHOLD` di `.env` (coba 0.15 / 0.18 / 0.22)
- Pastikan polygon dibuat di area slot yang benar

---

## 13. Auto-start (Opsional)

### Windows Task Scheduler
1. Buat file `start.bat`:
   ```bat
   @echo off
   cd /d "C:\path\to\TA_OpenCV"
   call venv\Scripts\activate
   python run_server.py
   ```
2. Task Scheduler → Create Task → trigger At log on → action `start.bat`.

### Linux systemd
File `/etc/systemd/system/parking.service`:
```ini
[Unit]
Description=Parking Detection
After=network.target mysql.service

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/TA_OpenCV
ExecStart=/path/to/TA_OpenCV/venv/bin/python run_server.py
Restart=always

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable parking
sudo systemctl start parking
```
