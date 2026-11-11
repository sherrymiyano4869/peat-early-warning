"use strict";
// timeseries.js: grafik deret waktu area pilot di halaman Monitoring. Membaca data/timeseries.json (scripts/09b_export_timeseries.py).
// Berdiri sendiri (tidak bergantung pada app.js). Berkas lokal, bukan dari zip web.
(function () {
  const SVGNS = "http://www.w3.org/2000/svg";
  const RANGES = [{ id: "90", label: "90 hari", days: 90 }, { id: "365", label: "1 tahun", days: 365 }, { id: "1096", label: "3 tahun", days: 1096 }];
  const COLORS = { line: "#2a78d6", bar: "#eb6834" };
  const H = 84, M = { l: 34, r: 8, t: 6, b: 15 };
  const DAY = 86400000;
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

  const el = (tag, attrs, text) => {
    const e = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([k, v]) => e.setAttribute(k, v));
    if (text !== undefined) e.textContent = text;
    return e;
  };
  const svg = (tag, attrs) => {
    const e = document.createElementNS(SVGNS, tag);
    Object.entries(attrs || {}).forEach(([k, v]) => e.setAttribute(k, v));
    return e;
  };
  const num = (v, unit) => {
    if (v === null || v === undefined) return "–";
    const d = Math.abs(v) < 1 ? 3 : (Math.abs(v) < 20 ? 1 : 0);
    return Number(v).toLocaleString("id-ID", { minimumFractionDigits: d, maximumFractionDigits: d }) + (unit ? " " + unit : "");
  };
  const dateLabel = t => { const d = new Date(t); return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`; };
  const shortLabel = t => { const d = new Date(t); return `${MONTHS[d.getUTCMonth()]} ${String(d.getUTCFullYear()).slice(2)}`; };

  function niceTicks(lo, hi) {
    if (lo === hi) { lo -= 1; hi += 1; }
    const span = hi - lo, raw = span / 3, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= raw) || raw;
    const t0 = Math.floor(lo / step) * step, out = [];
    for (let v = t0; v <= hi + step * 0.999; v += step) out.push(Number(v.toFixed(10)));
    return out;
  }

  function buildChart(s, width) {
    const box = el("div", { class: "ts-chart" });
    const head = el("div", { class: "ts-head" });
    head.appendChild(el("span", { class: "ts-title" }, s.title));
    const readout = el("span", { class: "ts-readout" });
    head.appendChild(readout);
    box.appendChild(head);
    if (s.status !== "tersedia" || !s.dates.length) {
      box.appendChild(el("div", { class: "ts-empty" }, "Belum tersedia. " + (s.note || "")));
      return { box, draw: () => {}, hover: () => {} };
    }
    const times = s.dates.map(d => Date.parse(d + "T00:00:00Z"));
    const root = svg("svg", { width: width, height: H, role: "img", "aria-label": s.title });
    box.appendChild(root);
    if (s.ref) {
      const key = el("div", { class: "ts-key" });
      key.appendChild(el("span", { class: "ts-keyline", style: `background:${COLORS.line}` }));
      key.appendChild(document.createTextNode("teramati "));
      key.appendChild(el("span", { class: "ts-keyline", style: "background:#9a9a94" }));
      key.appendChild(document.createTextNode(s.ref_label || "normal"));
      box.appendChild(key);
    }
    if (s.note) box.appendChild(el("div", { class: "small" }, s.note));
    const iw = width - M.l - M.r, ih = H - M.t - M.b;
    let x0 = 0, x1 = 1, sx = () => 0, sy = () => 0, lastIdx = -1;

    const setReadout = i => {
      if (i < 0) { readout.textContent = "tidak ada data pada rentang ini"; return; }
      const ref = s.ref && s.ref[i] !== null && s.ref[i] !== undefined ? ` (normal ${num(s.ref[i])})` : "";
      readout.textContent = "";
      readout.appendChild(el("b", {}, num(s.values[i], s.unit)));
      readout.appendChild(document.createTextNode(`${ref} · ${dateLabel(times[i])}`));
    };

    function draw(tEnd, days) {
      while (root.firstChild) root.removeChild(root.firstChild);
      x1 = tEnd; x0 = tEnd - days * DAY;
      const idx = times.map((t, i) => i).filter(i => times[i] >= x0 && times[i] <= x1);
      const vals = idx.map(i => s.values[i]).filter(v => v !== null && v !== undefined);
      const refs = s.ref ? idx.map(i => s.ref[i]).filter(v => v !== null && v !== undefined) : [];
      lastIdx = -1;
      for (let j = idx.length - 1; j >= 0; j--) if (s.values[idx[j]] !== null && s.values[idx[j]] !== undefined) { lastIdx = idx[j]; break; }
      setReadout(lastIdx);
      sx = t => M.l + (t - x0) / (x1 - x0) * iw;
      if (!vals.length) {
        const t = svg("text", { x: M.l + iw / 2, y: M.t + ih / 2, "text-anchor": "middle", class: "ts-tick" });
        t.textContent = "tidak ada data pada rentang ini"; root.appendChild(t); return;
      }
      const all = vals.concat(refs, s.threshold ? [s.threshold.value] : []);
      let lo = Math.min(...all), hi = Math.max(...all);
      if (s.kind === "bar" || s.id === "rain30" || s.id === "dry") lo = Math.min(0, lo);
      if (s.kind === "bar") hi = Math.max(hi, 4);
      const ticks = niceTicks(lo, hi);
      lo = ticks[0]; hi = ticks[ticks.length - 1];
      sy = v => M.t + (hi - v) / (hi - lo) * ih;
      ticks.forEach(v => {
        root.appendChild(svg("line", { x1: M.l, x2: M.l + iw, y1: sy(v), y2: sy(v), class: "ts-grid" }));
        const t = svg("text", { x: M.l - 4, y: sy(v) + 3, "text-anchor": "end", class: "ts-tick" });
        t.textContent = Number(v).toLocaleString("id-ID", { maximumFractionDigits: 2 }); root.appendChild(t);
      });
      [[x0, "start"], [(x0 + x1) / 2, "middle"], [x1, "end"]].forEach(([t, anchor]) => {
        const tx = svg("text", { x: sx(t), y: H - 3, "text-anchor": anchor, class: "ts-tick" });
        tx.textContent = days <= 120 ? dateLabel(t).replace(/ \d{4}$/, "") : shortLabel(t); root.appendChild(tx);
      });
      if (s.threshold) {
        root.appendChild(svg("line", { x1: M.l, x2: M.l + iw, y1: sy(s.threshold.value), y2: sy(s.threshold.value), class: "ts-thr" }));
        const t = svg("text", { x: M.l + 2, y: sy(s.threshold.value) - 3, "text-anchor": "start", class: "ts-tick" });
        t.textContent = s.threshold.label; root.appendChild(t);
      }
      const path = (arr, cls, color) => {
        let d = "", pen = false, prev = null;
        idx.forEach(i => {
          const v = arr[i];
          if (v === null || v === undefined || (prev !== null && times[i] - prev > 45 * DAY)) { pen = false; if (v === null || v === undefined) return; }
          d += (pen ? "L" : "M") + sx(times[i]).toFixed(1) + " " + sy(v).toFixed(1) + " "; pen = true; prev = times[i];
        });
        const p = svg("path", { d: d, class: cls }); if (color) p.setAttribute("stroke", color); root.appendChild(p);
      };
      if (s.kind === "bar") {
        const bw = Math.max(1, Math.min(24, iw / days - 0.6));
        idx.forEach(i => {
          const v = s.values[i]; if (!v) return;
          root.appendChild(svg("rect", { x: (sx(times[i]) - bw / 2).toFixed(1), y: sy(v).toFixed(1), width: bw.toFixed(1), height: Math.max(1, sy(0) - sy(v)).toFixed(1), fill: COLORS.bar }));
        });
      } else {
        if (s.ref) path(s.ref, "ts-ref");
        path(s.values, "ts-line", COLORS.line);
        if (vals.length <= 40) idx.forEach(i => {
          if (s.values[i] === null || s.values[i] === undefined) return;
          root.appendChild(svg("circle", { cx: sx(times[i]).toFixed(1), cy: sy(s.values[i]).toFixed(1), r: 3, fill: COLORS.line, stroke: "#fff", "stroke-width": 1.5 }));
        });
      }
      root.appendChild(svg("line", { x1: 0, x2: 0, y1: M.t, y2: M.t + ih, class: "ts-cross", visibility: "hidden" }));
    }

    function hover(t) {
      const cross = root.querySelector(".ts-cross");
      if (!cross) return;
      if (t === null) { cross.setAttribute("visibility", "hidden"); setReadout(lastIdx); return; }
      let best = -1, bestD = Infinity;
      times.forEach((ti, i) => {
        if (ti < x0 || ti > x1 || s.values[i] === null || s.values[i] === undefined) return;
        const d = Math.abs(ti - t); if (d < bestD) { bestD = d; best = i; }
      });
      if (best < 0 || bestD > 20 * DAY) { cross.setAttribute("visibility", "hidden"); readout.textContent = "tidak ada nilai di " + dateLabel(t); return; }
      cross.setAttribute("x1", sx(times[best])); cross.setAttribute("x2", sx(times[best])); cross.setAttribute("visibility", "visible");
      setReadout(best);
    }
    const timeAt = ev => { const r = root.getBoundingClientRect(); return x0 + Math.min(1, Math.max(0, (ev.clientX - r.left - M.l) / iw)) * (x1 - x0); };
    return { box, draw, hover, root, timeAt };
  }

  async function init() {
    const host = document.getElementById("timeseries");
    if (!host || location.protocol === "file:") return;
    let doc;
    try {
      const r = await fetch("data/timeseries.json", { cache: "no-cache" });
      if (!r.ok) throw new Error(String(r.status));
      doc = await r.json();
    } catch (e) {
      host.appendChild(el("div", { class: "small" }, "Deret waktu belum dibuat. Jalankan: python scripts/09b_export_timeseries.py (atau ./run_pipeline.sh peta)."));
      return;
    }
    host.appendChild(el("b", {}, "Deret waktu area pilot"));
    host.appendChild(el("div", { class: "small" }, `Ringkasan ${doc.area}, bukan nilai per sel. Arahkan kursor ke grafik untuk membaca nilai.`));
    const bar = el("div", { class: "ts-ranges", role: "group", "aria-label": "Rentang waktu" });
    host.appendChild(bar);
    const width = Math.max(220, host.clientWidth || 286);
    const charts = doc.series.map(s => buildChart(s, width));
    charts.forEach(c => host.appendChild(c.box));
    const tEnd = Math.max(...doc.series.filter(s => s.dates.length).map(s => Date.parse(s.dates[s.dates.length - 1] + "T00:00:00Z")));
    let current = "365";
    try { current = localStorage.getItem("ts-range") || current; } catch (e) { /* abaikan */ }
    const apply = id => {
      const rg = RANGES.find(r => r.id === id) || RANGES[1];
      current = rg.id;
      try { localStorage.setItem("ts-range", current); } catch (e) { /* abaikan */ }
      bar.querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.id === current)));
      charts.forEach(c => c.draw(tEnd, rg.days));
    };
    RANGES.forEach(rg => {
      const b = el("button", { type: "button", "data-id": rg.id }, rg.label);
      b.addEventListener("click", () => apply(rg.id));
      bar.appendChild(b);
    });
    charts.forEach(c => {
      if (!c.root) return;
      c.root.addEventListener("pointermove", ev => { const t = c.timeAt(ev); charts.forEach(o => o.hover(t)); });
      c.root.addEventListener("pointerleave", () => charts.forEach(o => o.hover(null)));
    });
    host.appendChild(el("a", { class: "small", href: "data/timeseries.json", download: "timeseries.json" }, "Unduh data deret waktu (JSON)"));
    apply(current);
  }

  if (typeof document !== "undefined") init();
})();
