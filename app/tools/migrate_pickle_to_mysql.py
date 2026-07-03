"""
One-shot migrasi polygon dari file pickle (CarParkPos) ke tabel MySQL `slots`.

Jalankan:
    python -m app.tools.migrate_pickle_to_mysql [path_pickle]

Default path: ./CarParkPos
"""

from __future__ import annotations

import os
import pickle
import sys

from app.db import repository as repo
from app.db.connection import SessionLocal


def main(path: str = "CarParkPos") -> None:
    if not os.path.exists(path):
        print(f"[!] File pickle tidak ditemukan: {path}")
        sys.exit(1)

    with open(path, "rb") as f:
        pos_list = pickle.load(f)

    if not isinstance(pos_list, list):
        print(f"[!] Format tidak dikenal di {path}")
        sys.exit(1)

    print(f"[i] Memuat {len(pos_list)} polygon dari {path}")

    inserted = 0
    skipped = 0
    with SessionLocal() as session:
        for i, polygon in enumerate(pos_list, start=1):
            code = f"S{i:03d}"
            if repo.get_slot_by_code(session, code) is not None:
                print(f"  - skip (sudah ada): {code}")
                skipped += 1
                continue
            # Validasi polygon
            try:
                poly = [[int(x), int(y)] for x, y in polygon]
            except Exception:
                print(f"  - skip (bentuk salah): index={i}")
                skipped += 1
                continue
            repo.create_slot(session, code, poly)
            print(f"  + insert {code} ({len(poly)} titik)")
            inserted += 1
        session.commit()

    print(f"[✓] Selesai. Inserted={inserted}, skipped={skipped}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "CarParkPos"
    main(path)
