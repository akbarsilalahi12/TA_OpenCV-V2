// Dashboard logic — fetch awal + WebSocket realtime + Chart.js

const $ = (sel) => document.querySelector(sel);

const state = {
  slots: new Map(),  // slot_id -> { slot_code, status, ratio }
  overrides: new Map(), // slot_id -> "FREE" | "FULL"
  chart: null,
  range: "24h",
};

// ============= Helper UI =============

function setConn(ok, text) {
  const dot = $("#conn-dot");
  const t = $("#conn-text");
  dot.classList.remove("bg-slate-500", "bg-emerald-500", "bg-rose-500");
  if (ok === true) dot.classList.add("bg-emerald-500");
  else if (ok === false) dot.classList.add("bg-rose-500");
  else dot.classList.add("bg-slate-500");
  t.textContent = text;
}

function renderCounters() {
  let free = 0, full = 0;
  for (const s of state.slots.values()) {
    if (s.status === "FREE") free++;
    else if (s.status === "FULL") full++;
  }
  const total = state.slots.size;
  $("#counter-free").textContent = free;
  $("#counter-full").textContent = full;
  $("#counter-total").textContent = total;
}

function slotCardHtml(slot) {
  const isFree = slot.status === "FREE";
  const isUnknown = !slot.status;
  const cls = isUnknown
    ? "bg-slate-700/30 border-slate-600 text-slate-300"
    : isFree
    ? "bg-emerald-500/10 border-emerald-500/40 text-emerald-200"
    : "bg-rose-500/10 border-rose-500/40 text-rose-200";
  const label = slot.status || "-";
  const ratio = (slot.ratio ?? 0).toFixed?.(2) ?? "0.00";
  const hasOverride = state.overrides.has(slot.slot_id);
  const overrideStatus = state.overrides.get(slot.slot_id);
  const freeActive = hasOverride && overrideStatus === "FREE" ? "ring-2 ring-emerald-400" : "";
  const fullActive = hasOverride && overrideStatus === "FULL" ? "ring-2 ring-rose-400" : "";
  return `
    <div class="slot-card border ${cls} rounded-lg px-2 py-2 text-center" data-slot-id="${slot.slot_id}">
      <div class="font-semibold text-sm">${slot.slot_code}</div>
      <div class="text-xs">${label}${hasOverride ? ' <span class="text-[10px] text-amber-400">(manual)</span>' : ""}</div>
      <div class="text-[10px] opacity-70">r=${ratio}</div>
      <div class="mt-1 flex gap-1 justify-center">
        <button data-action="free" class="btn-override text-[10px] px-1.5 py-0.5 rounded bg-emerald-700 hover:bg-emerald-600 text-white ${freeActive}">Bebas</button>
        <button data-action="full" class="btn-override text-[10px] px-1.5 py-0.5 rounded bg-rose-700 hover:bg-rose-600 text-white ${fullActive}">Penuh</button>
        <button data-action="auto" class="btn-override text-[10px] px-1.5 py-0.5 rounded bg-slate-600 hover:bg-slate-500 text-white ${!hasOverride ? "hidden" : ""}">Auto</button>
      </div>
    </div>
  `;
}

function renderSlotGrid() {
  const grid = $("#slot-grid");
  if (state.slots.size === 0) {
    grid.innerHTML = `<p class="col-span-full text-slate-400 text-sm">Belum ada slot. Buat polygon di tool kalibrasi.</p>`;
    return;
  }
  const arr = Array.from(state.slots.values()).sort((a, b) =>
    a.slot_code.localeCompare(b.slot_code)
  );
  grid.innerHTML = arr.map(slotCardHtml).join("");
}

function updateSlot(slot_id, patch) {
  const cur = state.slots.get(slot_id) || { slot_id };
  state.slots.set(slot_id, { ...cur, ...patch });
  // patch DOM tanpa rebuild semua
  const card = document.querySelector(`[data-slot-id="${slot_id}"]`);
  if (card) {
    const tmp = document.createElement("div");
    tmp.innerHTML = slotCardHtml(state.slots.get(slot_id)).trim();
    card.replaceWith(tmp.firstChild);
  } else {
    renderSlotGrid();
  }
  renderCounters();
}

// ============= Overrides =============

async function loadOverrides() {
  try {
    const r = await fetch("/api/slots/overrides");
    const j = await r.json();
    state.overrides = new Map(
      Object.entries(j.data || {}).map(([k, v]) => [parseInt(k), v])
    );
  } catch {
    state.overrides = new Map();
  }
}

// ============= Fetch awal =============

async function loadSlots() {
  try {
    const [res] = await Promise.all([
      fetch("/api/slots?active_only=true"),
      loadOverrides(),
    ]);
    const j = await res.json();
    state.slots.clear();
    for (const s of j.data) {
      state.slots.set(s.id, {
        slot_id: s.id,
        slot_code: s.slot_code,
        status: s.status,
        ratio: s.ratio,
      });
    }
    renderSlotGrid();
    renderCounters();
  } catch (e) {
    console.error("loadSlots error", e);
  }
}

async function loadHealthLoop() {
  setInterval(async () => {
    try {
      const res = await fetch("/health");
      const j = await res.json();
      $("#fps-text").textContent = `FPS: ${j.fps?.toFixed?.(1) ?? 0}`;
    } catch {
      $("#fps-text").textContent = "FPS: -";
    }
  }, 2000);
}

// ============= WebSocket =============

function connectWS() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/slots`);

  ws.addEventListener("open", () => setConn(true, "connected"));
  ws.addEventListener("close", () => {
    setConn(false, "disconnected, retry in 3s");
    setTimeout(connectWS, 3000);
  });
  ws.addEventListener("error", () => {
    setConn(false, "connection error");
  });

  ws.addEventListener("message", (e) => {
    try {
      const msg = JSON.parse(e.data);
      handleWSMessage(msg);
    } catch {}
  });
}

function handleWSMessage(msg) {
  switch (msg.type) {
    case "slot_changed": {
      const d = msg.data;
      updateSlot(d.slot_id, {
        slot_code: d.slot_code,
        status: d.status,
        ratio: d.ratio,
      });
      break;
    }
    case "summary_tick": {
      const d = msg.data;
      $("#counter-free").textContent = d.free;
      $("#counter-full").textContent = d.full;
      $("#counter-total").textContent = d.total;
      // Refresh chart soft (tidak setiap tick, biar tidak berat)
      break;
    }
    case "system_event":
      console.info("[system]", msg.data);
      break;
    case "ping":
      // ignore
      break;
  }
}

// ============= Chart =============

async function loadChart() {
  try {
    const res = await fetch(`/api/summary?range=${state.range}`);
    const j = await res.json();
    const labels = j.data.map((d) => new Date(d.time).toLocaleString());
    const free = j.data.map((d) => d.free);
    const full = j.data.map((d) => d.full);

    const ctx = $("#chart");
    if (state.chart) {
      state.chart.data.labels = labels;
      state.chart.data.datasets[0].data = free;
      state.chart.data.datasets[1].data = full;
      state.chart.update();
      return;
    }

    state.chart = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Free",
            data: free,
            borderColor: "#34d399",
            backgroundColor: "rgba(52,211,153,0.15)",
            tension: 0.25,
            fill: true,
          },
          {
            label: "Full",
            data: full,
            borderColor: "#fb7185",
            backgroundColor: "rgba(251,113,133,0.15)",
            tension: 0.25,
            fill: true,
          },
        ],
      },
      options: {
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: "#cbd5e1" } },
        },
        scales: {
          x: { ticks: { color: "#94a3b8", maxTicksLimit: 8 }, grid: { color: "#1e293b" } },
          y: { ticks: { color: "#94a3b8" }, grid: { color: "#1e293b" }, beginAtZero: true },
        },
      },
    });
  } catch (e) {
    console.error("loadChart error", e);
  }
}

// ============= Boot =============

document.addEventListener("DOMContentLoaded", () => {
  setConn(null, "connecting…");
  loadSlots();
  loadChart();
  loadHealthLoop();
  connectWS();

  $("#btn-refresh").addEventListener("click", loadSlots);
  $("#range-select").addEventListener("change", (e) => {
    state.range = e.target.value;
    loadChart();
  });

  // Override buttons — event delegation
  $("#slot-grid").addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-action]");
    if (!btn) return;
    const card = btn.closest("[data-slot-id]");
    if (!card) return;
    const slotId = parseInt(card.dataset.slotId);
    const action = btn.dataset.action;

    try {
      if (action === "auto") {
        await fetch(`/api/slots/${slotId}/override`, { method: "DELETE" });
        state.overrides.delete(slotId);
        // Re-render card to remove manual badge, hide Auto btn
        const el = document.querySelector(`[data-slot-id="${slotId}"]`);
        if (el) {
          const tmp = document.createElement("div");
          tmp.innerHTML = slotCardHtml(state.slots.get(slotId)).trim();
          el.replaceWith(tmp.firstChild);
        }
      } else {
        const status = action === "free" ? "FREE" : "FULL";
        await fetch(`/api/slots/${slotId}/override`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status }),
        });
        state.overrides.set(slotId, status);
        updateSlot(slotId, { status }); // updates state, re-renders card, calls renderCounters
      }
    } catch (err) {
      console.error("Override error", err);
    }
  });

  // Refresh chart tiap 60 detik
  setInterval(loadChart, 60_000);
});
