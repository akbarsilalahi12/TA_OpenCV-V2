# Move Manual Override (Full/Free) to Dashboard Slot Status

## Goal
Add manual override buttons (Bebas/Free, Penuh/Full, Auto) from admin page to the dashboard's Slot Status section. Each slot card gets action buttons to manually force FREE or FULL status, plus a button to revert to auto-detection.

## Context

**Current state:**
- `web/admin.html` — table with Bebas/Free, Penuh/Full, Auto, Hapus (delete), and toggle-active buttons per slot. Fetches overrides from `GET /api/slots/overrides`.
- `web/index.html` — dashboard with counter, live CCTV, slot cards grid, and chart.
- `web/js/dashboard.js` — renders slot cards, websocket updates, counters, chart.
- API routes in `app/api/routes_slots.py` already expose all needed endpoints:
  - `GET /api/slots/overrides` — returns `{data: {slot_id: "FREE"|"FULL", ...}}`
  - `POST /api/slots/{id}/override` — body `{status: "FREE"|"FULL"}`
  - `DELETE /api/slots/{id}/override` — clears override

**No changes needed to**: API, backend, admin page. Only dashboard JS and possibly CSS.

## Changes

### 1. `web/js/dashboard.js` — Add override capability

**State additions:**
- `state.overrides: Map<number, string>` (slot_id → "FREE"|"FULL")
- `loadOverrides()` — fetch `GET /api/slots/overrides`, populate map

**Modify `slotCardHtml()`:**
- Add 3 small action buttons in the card: **Bebas** (FREE), **Penuh** (FULL), **Auto** (clear override)
- Highlight active override button with a ring/active style
- Show `(manual)` badge next to status when slot has an override

**Modify `loadSlots()`:**
- Call `loadOverrides()` after fetching slots
- Pass override state through to card rendering

**Add event delegation on `#slot-grid`:**
- Click `.btn-override-free` → `POST /api/slots/{id}/override {status:"FREE"}`
- Click `.btn-override-full` → `POST /api/slots/{id}/override {status:"FULL"}`
- Click `.btn-override-auto` → `DELETE /api/slots/{id}/override`
- On success: update local state, re-render that card, update counters

**Persistence note:** Override is stored in-memory by `detection_loop.py`. Setting an override stops detection from overwriting that slot's status. The WebSocket does NOT broadcast override changes, so the dashboard will optimistically update locally after each action.

### 2. `web/css/style.css` — Optional

May need small styles for the override buttons to look good in compact cards.

### 3. `web/admin.html` — No change (keep existing override buttons)

The user said "pindahkan" (move), but removing from admin breaks existing workflow for users who manage slots. Keep admin intact.

## Slot Card Layout (before → after)

**Before:**
```
┌──────────────┐
│     A1       │
│    FREE      │
│   r=0.45     │
└──────────────┘
```

**After:**
```
┌──────────────────┐
│     A1   (manual)│
│    FREE          │
│   r=0.45         │
│ [Bebas][Penuh][Auto] │
└──────────────────┘
```

## Validation

1. Open dashboard → each slot card shows Bebas/Penuh/Auto buttons
2. Click Bebas → slot shows FREE with (manual) badge, button highlights
3. Click Penuh → slot shows FULL with (manual) badge, button changes highlight
4. Click Auto → override cleared, badge removed, button highlight removed
5. Open admin page → confirm override is reflected there too (shared in-memory state)
6. Refresh dashboard → overrides persist (loaded from API)
