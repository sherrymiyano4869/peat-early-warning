"use strict";
const DATA_DIR = "data/";

function fmt(x, d = 1) {
  return (x === null || x === undefined || Number.isNaN(x)) ? "–" : Number(x).toFixed(d);
}

function probColor(p) {
  if (p === null || p === undefined || Number.isNaN(p)) return "#888888";
  if (p < 0.2) return "#2b83ba";
  if (p < 0.4) return "#abdda4";
  if (p < 0.6) return "#ffffbf";
  if (p < 0.8) return "#fdae61";
  return "#d7191c";
}

function wlColor(cm) {
  if (cm === null || cm === undefined || Number.isNaN(cm)) return "#888888";
  if (cm >= -40) return "#2b83ba";
  if (cm >= -80) return "#abdda4";
  if (cm >= -120) return "#ffffbf";
  if (cm >= -160) return "#fdae61";
  return "#d7191c";
}

function sparklinePath(values, w, h, pad = 2) {
  const pts = values.map((v, i) => [i, v]).filter(p => p[1] !== null && p[1] !== undefined && !Number.isNaN(p[1]));
  if (pts.length < 2) return "";
  const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const sx = (w - 2 * pad) / Math.max(x1 - x0, 1), sy = (h - 2 * pad) / Math.max(y1 - y0, 1e-9);
  return pts.map((p, k) => (k === 0 ? "M" : "L") + (pad + (p[0] - x0) * sx).toFixed(1) + " " + (h - pad - (p[1] - y0) * sy).toFixed(1)).join(" ");
}

function validationBadge(v) {
  if (!v || !v.available) {
    return { cls: "warn", text: "Validasi belum tersedia. Perlakukan prediksi sebagai prototipe." };
  }
  const skills = [v.skill_h7, v.skill_h14].filter(s => s !== null && s !== undefined && !Number.isNaN(s));
  const worst = skills.length ? Math.min(...skills) : null;
  const cover = v.coverage_q10_q90_h7;
  const covTxt = (cover === null || cover === undefined) ? "" : ` Rentang q10–q90 mencakup ${fmt(cover * 100, 0)}% kenyataan (target 80%).`;
  if (worst === null || v.cap_class === 0) {
    return { cls: "bad", text: `Model belum terbukti lebih baik daripada persistensi (skill ${fmt(worst, 2)}). Kepercayaan: rendah.${covTxt}` };
  }
  if (v.cap_class === 1) {
    return { cls: "warn", text: `Skill kecil terhadap persistensi (${fmt(worst, 2)}). Kepercayaan: sedang.${covTxt}` };
  }
  return { cls: "ok", text: `Skill ${fmt(worst, 2)} terhadap persistensi pada walk-forward. Kepercayaan: tinggi.${covTxt}` };
}

function predictionTable(pred) {
  const rows = ["h7", "h14"].filter(k => pred && pred[k]).map(k => {
    const p = pred[k];
    return `<tr><td>${k.slice(1)} hari</td><td>${fmt(p.delta_med)}</td><td>${fmt(p.delta_q10)} s/d ${fmt(p.delta_q90)}</td>` +
           `<td>${fmt(p.p_turun10 === null ? null : p.p_turun10 * 100, 0)}%</td><td>${fmt(p.p_turun10_basis === null ? null : p.p_turun10_basis * 100, 0)}%</td></tr>`;
  });
  if (!rows.length) return "<div class=\"small\">Belum ada prediksi untuk stasiun ini.</div>";
  return "<table class=\"pred\"><tr><th>Horizon</th><th>&Delta; (cm)</th><th>q10 s/d q90</th><th>P(turun&ge;10)</th><th>basis</th></tr>" + rows.join("") + "</table>";
}

function legendHtml(layer) {
  if (!layer) return "";
  const lg = layer.legend;
  if (lg.type === "categorical") {
    return `<b>${layer.title}</b><br>` + lg.items.map(i => `<span class="swatch" style="background:${i.color}"></span>${i.label}`).join("<br>");
  }
  const bar = `linear-gradient(to right, ${lg.colors.join(", ")})`;
  return `<b>${layer.title}</b><div class="bar" style="background:${bar}"></div>` +
         `<div class="ends"><span>${fmt(lg.min, 1)}</span><span>${layer.unit}</span><span>${fmt(lg.max, 1)}</span></div>`;
}

function startupHint(protocol, message) {
  if (protocol === "file:") {
    return "Halaman dibuka lewat berkas (file://), dan peramban memblokir pengambilan data. Jalankan di terminal: " +
           "python -m http.server -d webmap 8000, lalu buka http://localhost:8000";
  }
  return "Gagal memuat data: " + message + ". Pastikan python scripts/09_export_web.py sudah dijalankan dan folder webmap/data ada.";
}

async function getJson(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(url + " -> " + r.status);
  return r.json();
}

async function main() {
  const map = L.map("map").setView([-1.3, 104.0], 8);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "&copy; OpenStreetMap contributors" }).addTo(map);
  if (location.protocol === "file:") throw new Error("file-protocol");
  const manifest = await getJson(DATA_DIR + "manifest.json");
  document.getElementById("title").textContent = manifest.title;
  document.getElementById("meta").innerHTML =
    `Versi ${manifest.version} &middot; dibuat ${manifest.generated_at}<br>Data sampai ${manifest.data_through || "–"} &middot; tanggal terbit prediksi ${manifest.issue_date || "–"}`;
  const badge = validationBadge(manifest.validation);
  const badgeEl = document.getElementById("badge");
  badgeEl.className = "badge " + badge.cls;
  badgeEl.textContent = badge.text;
  document.getElementById("attrib").innerHTML = "<p>" + manifest.attribution.join("</p><p>") + "</p><p><b>" + manifest.disclaimer + "</b></p>";

  map.setView(manifest.center, 11);

  const overlays = {}, byTitle = {};
  let opacity = 0.7;
  manifest.layers.forEach(l => {
    const ov = L.imageOverlay(DATA_DIR + l.file, l.bounds, { opacity: opacity });
    overlays[l.title] = ov;
    byTitle[l.title] = { layer: l, ov: ov };
    if (l.default) ov.addTo(map);
  });
  const legendEl = document.getElementById("legend");
  const firstDefault = manifest.layers.find(l => l.default);
  legendEl.innerHTML = legendHtml(firstDefault);

  const gj = await getJson(DATA_DIR + manifest.stations.file);
  let mode = "wl";
  const colorFor = f => mode === "wl" ? wlColor(f.properties.wl_last_cm)
    : probColor(f.properties.pred && f.properties.pred.h14 ? f.properties.pred.h14.p_turun10 : null);
  const markers = L.geoJSON(gj, {
    pointToLayer: (f, ll) => L.circleMarker(ll, { radius: 7, weight: 1, color: "#222", fillOpacity: 0.9, fillColor: colorFor(f) }),
    onEachFeature: (f, layer) => {
      layer.bindPopup("Memuat...");
      layer.on("click", async () => {
        const p = f.properties;
        let spark = "";
        try {
          const s = await getJson(DATA_DIR + manifest.stations.series_dir + p.id + ".json");
          const path = sparklinePath(s.wl_cm, 220, 50);
          spark = path ? `<svg width="220" height="50" style="background:#f4f4f4"><path d="${path}" fill="none" stroke="#1f78b4" stroke-width="1.5"/></svg>` +
                         `<div class="small">muka air harian, ${s.dates[0]} s/d ${s.dates[s.dates.length - 1]}</div>` : "";
        } catch (e) { spark = "<div class=\"small\">Deret waktu tidak tersedia.</div>"; }
        layer.setPopupContent(`<b>${p.name}</b><br><span class="small">${p.id} &middot; ${p.region}</span><br>` +
          `Terakhir ${p.last_date || "–"}: ${fmt(p.wl_last_cm)} cm (perubahan 7 hari ${fmt(p.wl_d7_cm)} cm)<br>${spark}` +
          `<div style="margin-top:4px"><b>Prediksi (prototipe)</b></div>${predictionTable(p.pred)}` +
          `<div class="small">&Delta; = perubahan muka air; basis = frekuensi kejadian di data latih.</div>`);
      });
    }
  }).addTo(map);

  L.control.layers(null, Object.assign({}, overlays, { "Stasiun": markers }), { collapsed: false }).addTo(map);
  map.on("overlayadd", e => { if (byTitle[e.name]) legendEl.innerHTML = legendHtml(byTitle[e.name].layer); });

  document.getElementById("opacity").addEventListener("input", e => {
    opacity = Number(e.target.value);
    Object.values(overlays).forEach(o => o.setOpacity(opacity));
  });
  document.querySelectorAll("input[name=mode]").forEach(r => r.addEventListener("change", e => {
    mode = e.target.value;
    markers.eachLayer(l => l.setStyle({ fillColor: colorFor(l.feature) }));
  }));
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { fmt, probColor, wlColor, sparklinePath, validationBadge, predictionTable, legendHtml, startupHint };
} else {
  main().catch(err => {
    document.getElementById("title").textContent = "Data belum dapat dimuat";
    const hint = startupHint(location.protocol, err.message);
    document.getElementById("meta").textContent = hint;
    const badgeEl = document.getElementById("badge");
    badgeEl.className = "badge bad";
    badgeEl.textContent = hint;
  });
}
