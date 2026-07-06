"""
Parking Polygon Picker — versi MySQL.

- Sumber & target data: tabel `slots` (bukan file pickle lagi).
- Kontrol:
    Double click LMB : Tambah polygon (auto slot_code S###)
    Drag titik       : Resize
    Drag badan       : Pindah polygon
    Right click      : Soft delete polygon
    Q / Esc          : Keluar
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Tuple

import cv2
import numpy as np

from app.config import settings
from app.db import repository as repo
from app.db.connection import SessionLocal


log = logging.getLogger(__name__)

POINT_RADIUS = 8


# ============= State =============

class PickerState:
    """In-memory state. Disinkronisasi ke DB pada setiap perubahan."""

    def __init__(self) -> None:
        # list of dict: {id, slot_code, polygon: [[x,y],...]}
        self.slots: List[Dict] = []
        self.selected_point: Tuple[int, int] | None = None  # (slot_idx, point_idx)
        self.selected_polygon: int | None = None  # slot_idx
        self.drag_offset: Tuple[int, int] = (0, 0)
        self.dirty: bool = False  # ada perubahan yang belum di-save

    def reload(self) -> None:
        with SessionLocal() as s:
            slots = repo.list_slots(s, active_only=True)
            self.slots = [
                {"id": x.id, "slot_code": x.slot_code, "polygon": list(x.polygon_json)}
                for x in slots
            ]
        log.info("Loaded %d slots from MySQL", len(self.slots))

    def save_slot(self, idx: int) -> None:
        item = self.slots[idx]
        with SessionLocal() as s:
            repo.update_slot(s, item["id"], polygon=item["polygon"])
            s.commit()

    def add_slot(self, polygon: List[List[int]]) -> None:
        with SessionLocal() as s:
            code = repo.auto_next_slot_code(s)
            slot = repo.create_slot(s, code, polygon)
            s.commit()
            self.slots.append({
                "id": slot.id,
                "slot_code": slot.slot_code,
                "polygon": polygon,
            })
        log.info("Added slot %s", code)

    def delete_slot(self, idx: int) -> None:
        item = self.slots[idx]
        with SessionLocal() as s:
            repo.update_slot(s, item["id"], slot_code=f"_DEL_{item['id']}")
            repo.soft_delete_slot(s, item["id"])
            s.commit()
        log.info("Soft-deleted slot %s", item["slot_code"])
        self.slots.pop(idx)


# ============= Mouse handler =============

def make_mouse_handler(state: PickerState):
    def on_mouse(event, x, y, flags, params):
        # Double click = tambah polygon
        if event == cv2.EVENT_LBUTTONDBLCLK:
            w, h = 120, 60
            polygon = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
            state.add_slot(polygon)
            return

        # LMB down — pilih point atau polygon body
        if event == cv2.EVENT_LBUTTONDOWN:
            for si, slot in enumerate(state.slots):
                for pj, pt in enumerate(slot["polygon"]):
                    px, py = pt
                    if (x - px) ** 2 + (y - py) ** 2 < (POINT_RADIUS + 5) ** 2:
                        state.selected_point = (si, pj)
                        return

            for si, slot in enumerate(state.slots):
                pts = np.array(slot["polygon"], dtype=np.int32)
                if cv2.pointPolygonTest(pts, (x, y), False) >= 0:
                    state.selected_polygon = si
                    cx = int(np.mean(pts[:, 0]))
                    cy = int(np.mean(pts[:, 1]))
                    state.drag_offset = (x - cx, y - cy)
                    return
            return

        # Drag
        if event == cv2.EVENT_MOUSEMOVE:
            if state.selected_point is not None:
                si, pj = state.selected_point
                state.slots[si]["polygon"][pj] = [x, y]
                state.dirty = True
                return
            if state.selected_polygon is not None:
                si = state.selected_polygon
                pts = np.array(state.slots[si]["polygon"], dtype=np.int32)
                cx = int(np.mean(pts[:, 0]))
                cy = int(np.mean(pts[:, 1]))
                dx = x - cx - state.drag_offset[0]
                dy = y - cy - state.drag_offset[1]
                for k in range(len(state.slots[si]["polygon"])):
                    state.slots[si]["polygon"][k][0] += dx
                    state.slots[si]["polygon"][k][1] += dy
                state.dirty = True
                return
            return

        # Release — commit ke DB
        if event == cv2.EVENT_LBUTTONUP:
            target_idx = None
            if state.selected_point is not None:
                target_idx = state.selected_point[0]
            elif state.selected_polygon is not None:
                target_idx = state.selected_polygon
            state.selected_point = None
            state.selected_polygon = None
            if target_idx is not None and state.dirty:
                state.save_slot(target_idx)
                state.dirty = False
            return

        # Right click = delete
        if event == cv2.EVENT_RBUTTONDOWN:
            for si, slot in enumerate(state.slots):
                pts = np.array(slot["polygon"], dtype=np.int32)
                if cv2.pointPolygonTest(pts, (x, y), False) >= 0:
                    state.delete_slot(si)
                    return

    return on_mouse


# ============= RTSP loop =============

def _open_rtsp() -> cv2.VideoCapture | None:
    cap = cv2.VideoCapture(settings.rtsp_url, cv2.CAP_FFMPEG)
    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass
    if not cap.isOpened():
        cap.release()
        return None
    return cap


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    state = PickerState()
    state.reload()

    cap = _open_rtsp()

    win = "Parking Polygon Picker (MySQL)"
    cv2.namedWindow(win)
    cv2.setMouseCallback(win, make_mouse_handler(state))

    target_size = (settings.frame_width, settings.frame_height)
    print("Kontrol:")
    print("  Double click : tambah polygon")
    print("  Drag titik   : resize")
    print("  Drag badan   : pindah")
    print("  Right click  : hapus")
    print("  R            : reload dari DB")
    print("  Q / Esc      : keluar")

    while True:
        if cap is None or not cap.isOpened():
            print("Reconnecting RTSP...")
            time.sleep(2)
            cap = _open_rtsp()
            continue

        cap.grab()
        ret, frame = cap.read()
        if not ret or frame is None:
            cap.release()
            cap = None
            continue

        frame = cv2.resize(frame, target_size)

        # Draw all polygons
        for slot in state.slots:
            pts = np.array(slot["polygon"], dtype=np.int32)
            cv2.polylines(frame, [pts], True, (0, 0, 255), 2)
            for p in slot["polygon"]:
                cv2.circle(frame, tuple(p), POINT_RADIUS, (0, 255, 0), -1)
            cx = int(np.mean(pts[:, 0]))
            cy = int(np.mean(pts[:, 1]))
            cv2.putText(frame, slot["slot_code"], (cx - 20, cy),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        # Help overlay
        text = "DblClick:Add  Drag pt:Resize  Drag body:Move  RClick:Del  R:Reload  Q:Exit"
        cv2.rectangle(frame, (5, 5), (1100, 35), (0, 0, 0), -1)
        cv2.putText(frame, text, (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 1)

        cv2.imshow(win, frame)

        key = cv2.waitKey(1) & 0xFF
        if key in (27, ord("q")):
            break
        if key in (ord("r"), ord("R")):
            state.reload()

    if cap:
        cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
