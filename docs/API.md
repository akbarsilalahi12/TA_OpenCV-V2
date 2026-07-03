# API SPECIFICATION

Spesifikasi REST API + WebSocket untuk sistem deteksi slot parkir.

> **Base URL** (lokal): `http://192.168.x.x:8000`  
> **Swagger UI** otomatis tersedia di `/docs`  
> **OpenAPI JSON** di `/openapi.json`

---

## 1. Konvensi

- Semua response menggunakan JSON kecuali `/video_feed` (MJPEG).
- Format waktu: **ISO 8601 UTC**, contoh `2026-05-28T17:42:00Z`.
- Field error mengikuti standar FastAPI:
  ```json
  { "detail": "Slot not found" }
  ```
- HTTP status:
  - `200 OK` — sukses
  - `201 Created` — resource dibuat
  - `204 No Content` — sukses tanpa body (DELETE)
  - `400 Bad Request` — validasi gagal
  - `404 Not Found` — resource tidak ada
  - `500 Internal Server Error` — error server

---

## 2. Daftar Endpoint

| Method | Path | Fungsi |
|---|---|---|
| GET    | `/`                  | Halaman dashboard (HTML) |
| GET    | `/admin`             | Halaman admin (HTML, opsional) |
| GET    | `/health`            | Health check |
| GET    | `/video_feed`        | MJPEG stream live |
| GET    | `/api/slots`         | Daftar slot + status terkini |
| GET    | `/api/slots/{id}`    | Detail satu slot |
| POST   | `/api/slots`         | Buat slot baru |
| PUT    | `/api/slots/{id}`    | Update polygon slot |
| DELETE | `/api/slots/{id}`    | Soft delete slot |
| GET    | `/api/status`        | Ringkasan free/full/total |
| GET    | `/api/history`       | Log historis perubahan status |
| GET    | `/api/summary`       | Snapshot agregat untuk chart |
| WS     | `/ws/slots`          | WebSocket realtime |

---

## 3. Endpoint Detail

### 3.1 GET `/health`

Health check untuk monitoring.

**Response 200**
```json
{
  "status": "ok",
  "rtsp_connected": true,
  "db_connected": true,
  "fps": 12.4,
  "uptime_seconds": 3245
}
```

---

### 3.2 GET `/video_feed`

Live video stream dalam format **MJPEG** (`multipart/x-mixed-replace; boundary=frame`).

**Cara pakai di HTML:**
```html
<img src="/video_feed" alt="Live CCTV" />
```

Tiap frame adalah JPEG dengan overlay polygon slot + label status.

---

### 3.3 GET `/api/slots`

Daftar semua slot aktif beserta status terkini.

**Query parameter:**
| Param | Tipe | Default | Catatan |
|---|---|---|---|
| `active_only` | bool | `true` | filter slot aktif saja |

**Response 200**
```json
{
  "data": [
    {
      "id": 1,
      "slot_code": "A1",
      "polygon": [[120,200],[240,200],[240,260],[120,260]],
      "status": "FREE",
      "ratio": 0.045,
      "updated_at": "2026-05-28T17:42:00Z"
    },
    {
      "id": 2,
      "slot_code": "A2",
      "polygon": [[260,200],[380,200],[380,260],[260,260]],
      "status": "FULL",
      "ratio": 0.342,
      "updated_at": "2026-05-28T17:41:58Z"
    }
  ],
  "total": 2
}
```

---

### 3.4 GET `/api/slots/{id}`

**Response 200**
```json
{
  "id": 1,
  "slot_code": "A1",
  "polygon": [[120,200],[240,200],[240,260],[120,260]],
  "is_active": true,
  "status": "FREE",
  "ratio": 0.045,
  "created_at": "2026-05-20T10:00:00Z",
  "updated_at": "2026-05-28T17:42:00Z"
}
```

**Response 404**
```json
{ "detail": "Slot not found" }
```

---

### 3.5 POST `/api/slots`

Buat slot parkir baru.

**Request body**
```json
{
  "slot_code": "A3",
  "polygon": [[400,200],[520,200],[520,260],[400,260]]
}
```

**Validasi:**
- `slot_code`: string 1-20 karakter, unik.
- `polygon`: array dengan minimal 3 titik, tiap titik `[x, y]` integer.

**Response 201**
```json
{
  "id": 3,
  "slot_code": "A3",
  "polygon": [[400,200],[520,200],[520,260],[400,260]],
  "is_active": true,
  "created_at": "2026-05-28T17:50:00Z"
}
```

**Response 400** (slot_code duplikat)
```json
{ "detail": "slot_code 'A3' already exists" }
```

---

### 3.6 PUT `/api/slots/{id}`

Update polygon dan/atau kode slot.

**Request body** (semua field opsional)
```json
{
  "slot_code": "A3-renamed",
  "polygon": [[410,210],[520,210],[520,270],[410,270]],
  "is_active": true
}
```

**Response 200** — slot setelah update.

---

### 3.7 DELETE `/api/slots/{id}`

Soft delete (`is_active = 0`). Slot tidak dihapus permanen agar log historis tetap utuh.

**Response 204** — no content.

> Untuk hard delete, gunakan parameter `?hard=true` (admin only, hati-hati).

---

### 3.8 GET `/api/status`

Ringkasan cepat untuk header dashboard.

**Response 200**
```json
{
  "total_slot": 50,
  "free_slot": 32,
  "full_slot": 18,
  "occupancy_rate": 0.36,
  "as_of": "2026-05-28T17:42:00Z"
}
```

---

### 3.9 GET `/api/history`

Log historis perubahan status.

**Query parameter:**
| Param | Tipe | Default | Catatan |
|---|---|---|---|
| `slot_id` | int | — | filter slot tertentu |
| `from` | ISO datetime | 24 jam lalu | mulai |
| `to`   | ISO datetime | sekarang | akhir |
| `limit` | int | 100 | maksimal 1000 |
| `offset` | int | 0 | paginasi |

**Response 200**
```json
{
  "data": [
    {
      "id": 1024,
      "slot_id": 1,
      "slot_code": "A1",
      "status": "FULL",
      "ratio": 0.345,
      "detected_at": "2026-05-28T17:35:12Z"
    },
    {
      "id": 1023,
      "slot_id": 1,
      "slot_code": "A1",
      "status": "FREE",
      "ratio": 0.052,
      "detected_at": "2026-05-28T16:48:01Z"
    }
  ],
  "total": 2
}
```

---

### 3.10 GET `/api/summary`

Data agregat untuk chart historis.

**Query parameter:**
| Param | Tipe | Default | Catatan |
|---|---|---|---|
| `range` | enum: `1h`, `6h`, `24h`, `7d`, `30d` | `24h` | rentang |
| `bucket` | enum: `minute`, `hour`, `day` | otomatis dari `range` | granularitas |

**Response 200**
```json
{
  "range": "24h",
  "bucket": "hour",
  "data": [
    { "time": "2026-05-28T00:00:00Z", "free": 40, "full": 10, "total": 50 },
    { "time": "2026-05-28T01:00:00Z", "free": 38, "full": 12, "total": 50 },
    { "time": "2026-05-28T02:00:00Z", "free": 35, "full": 15, "total": 50 }
  ]
}
```

---

### 3.11 WebSocket `/ws/slots`

Push realtime perubahan status slot.

**Connect (JS):**
```js
const ws = new WebSocket(`ws://${location.host}/ws/slots`);

ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  console.log(msg);
};
```

**Pesan `slot_changed`** (dikirim hanya saat status berubah)
```json
{
  "type": "slot_changed",
  "data": {
    "slot_id": 1,
    "slot_code": "A1",
    "status": "FULL",
    "ratio": 0.345,
    "at": "2026-05-28T17:42:00Z"
  }
}
```

**Pesan `summary_tick`** (dikirim tiap N detik untuk update counter)
```json
{
  "type": "summary_tick",
  "data": {
    "free": 32,
    "full": 18,
    "total": 50,
    "at": "2026-05-28T17:42:00Z"
  }
}
```

**Pesan `system_event`** (event sistem)
```json
{
  "type": "system_event",
  "data": {
    "event_type": "RTSP_RECONNECT",
    "message": "Reconnected after 3.2s",
    "at": "2026-05-28T17:43:00Z"
  }
}
```

**Heartbeat:** server kirim `{"type":"ping"}` tiap 30 detik. Client balas `{"type":"pong"}`.

---

## 4. Contoh Pemakaian

### 4.1 cURL — list slot
```bash
curl http://192.168.18.50:8000/api/slots
```

### 4.2 cURL — buat slot baru
```bash
curl -X POST http://192.168.18.50:8000/api/slots \
  -H "Content-Type: application/json" \
  -d '{"slot_code":"B1","polygon":[[100,300],[220,300],[220,360],[100,360]]}'
```

### 4.3 JavaScript — fetch status & render
```js
async function loadStatus() {
  const res = await fetch('/api/status');
  const s = await res.json();
  document.getElementById('free-count').textContent = s.free_slot;
  document.getElementById('total-count').textContent = s.total_slot;
}
loadStatus();
```

### 4.4 JavaScript — chart historis
```js
const res = await fetch('/api/summary?range=24h&bucket=hour');
const { data } = await res.json();

new Chart(ctx, {
  type: 'line',
  data: {
    labels: data.map(d => d.time),
    datasets: [
      { label: 'Full', data: data.map(d => d.full) },
      { label: 'Free', data: data.map(d => d.free) }
    ]
  }
});
```

---

## 5. Pydantic Schema (referensi implementasi)

```python
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from datetime import datetime

class SlotIn(BaseModel):
    slot_code: str = Field(..., min_length=1, max_length=20)
    polygon: List[List[int]] = Field(..., min_length=3)

class SlotUpdate(BaseModel):
    slot_code: Optional[str] = Field(None, min_length=1, max_length=20)
    polygon: Optional[List[List[int]]] = None
    is_active: Optional[bool] = None

class SlotOut(BaseModel):
    id: int
    slot_code: str
    polygon: List[List[int]]
    is_active: bool
    status: Optional[Literal["FREE", "FULL"]] = None
    ratio: Optional[float] = None
    created_at: datetime
    updated_at: datetime

class StatusSummary(BaseModel):
    total_slot: int
    free_slot: int
    full_slot: int
    occupancy_rate: float
    as_of: datetime
```

---

## 6. Error Handling

| HTTP | Kasus | Contoh Body |
|---|---|---|
| 400 | Validasi pydantic gagal | `{"detail":[{"loc":["body","polygon"],"msg":"min_length","type":"too_short"}]}` |
| 400 | `slot_code` duplikat | `{"detail":"slot_code 'A1' already exists"}` |
| 404 | Slot tidak ada | `{"detail":"Slot not found"}` |
| 500 | DB / RTSP error | `{"detail":"Internal server error"}` |

---

## 7. Pertimbangan Keamanan

- API binding `0.0.0.0` membuat server dapat diakses **siapa saja di LAN**. Pastikan jaringan terpercaya.
- Tidak ada autentikasi di iterasi ini. Untuk produksi, tambah:
  - API key sederhana di header `X-API-Key`
  - Atau JWT untuk endpoint admin (`POST/PUT/DELETE /api/slots`)
- Endpoint `?hard=true` pada DELETE slot harus dilindungi.
- Rate limit (mis. `slowapi`) opsional untuk mencegah abuse.
