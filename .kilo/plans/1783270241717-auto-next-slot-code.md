# Plan: auto_next_slot_code — fill gap (reuse deleted slot number)

## Goal

`auto_next_slot_code` harus mengisi nomor terkecil yg tersedia (reuse gap dari slot yg dihapus), bukan selalu increment.

## Behavior yang diinginkan

| Keadaan active slots | Slot baru |
|---|---|
| (kosong) | S001 |
| S001, S002 | S003 |
| S001 (S002 dihapus) | S002 |
| S001, S002, S004 | S003 |
| S001, S002, S003 | S004 |
| S001 dihapus, S002 dihapus | S001 |

## File yang diubah

`app/db/repository.py` — fungsi `auto_next_slot_code`

## Logika baru

1. Query `slot_code` dari semua slot **aktif** (`is_active == 1`)
2. Ekstrak suffix numerik ke `set[int]`
3. Cari n ≥ 1 terkecil yg **tidak** ada di set
4. Return `f"{prefix}{n:03d}"`

## Kode final

```python
def auto_next_slot_code(session: Session, prefix: str = "S") -> str:
    """
    Generate slot_code berikutnya, format S001, S002, ...
    Mengisi nomor terkecil yg tersedia (reuse gap dari slot yg dihapus).
    """
    codes = session.scalars(
        select(Slot.slot_code).where(Slot.is_active == 1)
    ).all()
    used: set[int] = set()
    for code in codes:
        if code.startswith(prefix):
            try:
                used.add(int(code[len(prefix):]))
            except ValueError:
                pass
    n = 1
    while n in used:
        n += 1
    return f"{prefix}{n:03d}"
```

## Validasi

- `pytest` — 19 test harus lulus
- Cek manual via `run_picker.py`:
  1. Buat 2 slot → S001, S002
  2. Hapus S002
  3. Buat baru → S002 (reuse)
  4. Hapus S001
  5. Buat baru → S001 (reuse)
