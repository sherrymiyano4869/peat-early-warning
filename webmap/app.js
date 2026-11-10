"use strict";
const DATA_DIR = "data/";
const TRANSPARENT_TILE = "data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==";

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

// ---- kerawanan tiga tingkat -------------------------------------------------
function levelForZoom(levels, z) {
  return (levels || []).find(l => z >= l.minZoom && z <= l.maxZoom) || null;
}

function levelLabel(levels, z) {
  const lv = levelForZoom(levels, z);
  return lv ? lv.label : "–";
}

function classColor(classes, id) {
  const c = (classes || []).find(x => x.id === id);
  return c ? c.color : "#cccccc";
}

function unitStyle(classes, props) {
  return { fillColor: classColor(classes, props.kelas), fillOpacity: 0.85, color: "#555555", weight: 0.8 };
}

function boundaryStyle(kind) {
  if (kind === "khg") return { color: "#2d2d2d", weight: 1.6, dashArray: "6 4", fill: false };
  if (kind === "admin") return { color: "#8a8a8a", weight: 0.9, fill: false };
  return { color: "#3b83bd", weight: 0.7, opacity: 0.85 };   // kanal: garis biru tipis, bukan peta panas
}

function unitPopupHtml(p, k) {
  return `<b>${p.nama}</b><br><span class="small">${k.unit_type}</span><br>` +
         `Kelas: <b>${p.label}</b> (indeks rata-rata ${fmt(p.indeks_rata2, 2)})<br>` +
         `Bagian sel kelas tinggi atau sangat tinggi: ${fmt(p.bagian_tinggi * 100, 0)}%<br>` +
         `Cakupan data: ${fmt(p.cakupan * 100, 0)}% &middot; kepercayaan rendah: ${fmt(p.kepercayaan_rendah * 100, 0)}%<br>` +
         `<div class="small">Ringkasan tingkat unit; perbesar peta untuk melihat sel.</div>`;
}

function kerawananLegendHtml(k) {
  if (!k) return "";
  const cls = k.classes.map(c => `<span class="swatch" style="background:${c.color}"></span>${c.label}`).join("<br>");
  const conf = `<span class="swatch" style="background:#bd0026"></span>pekat: kepercayaan tinggi<br>` +
               `<span class="swatch" style="background:#bd0026;opacity:.7"></span>agak transparan: sedang<br>` +
               `<span class="swatch hatch" style="background-color:#fd8d3c;opacity:.6"></span>transparan dan diarsir: rendah`;
  const mode = k.mode === "struktural" ? "Hanya kerentanan struktural (belum ada tekanan dinamis)." : "Kerentanan struktural + tekanan dinamis.";
  return `<b>${k.title}</b> <span class="small">(indeks relatif)</span><br>${cls}<div class="small" style="margin-top:4px">${mode}</div>` +
         `<div style="margin-top:6px"><b>Kepercayaan</b><br>${conf}</div>` +
         `<div class="small" style="margin-top:4px">${k.disclaimer}</div>`;
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
  // Peta dasar OSM standar (gratis, tanpa API key); dibuat abu muda lewat CSS .basemap-gray. CARTO kini meminta API key.
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    { maxZoom: 19, className: "basemap-gray",
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' }).addTo(map);
  L.control.scale({ metric: true, imperial: false }).addTo(map);
  if (location.protocol === "file:") throw new Error("file-protocol");
  const manifest = await getJson(DATA_DIR + "manifest.json");
  const $ = id => document.getElementById(id);
  $("title").textContent = manifest.title;
  $("meta").innerHTML =
    `Versi ${manifest.version} &middot; dibuat ${manifest.generated_at}<br>Data sampai ${manifest.data_through || "–"} &middot; tanggal terbit prediksi ${manifest.issue_date || "–"}`;
  const badge = validationBadge(manifest.validation);
  $("badge").className = "badge " + badge.cls;
  $("badge").textContent = badge.text;
  $("attrib").innerHTML = "<p>" + manifest.attribution.join("</p><p>") + "</p><p><b>" + manifest.disclaimer + "</b></p>";
  map.setView(manifest.center, 11);
  map.createPane("kerawananPane"); map.getPane("kerawananPane").style.zIndex = 250;
  map.createPane("unitPane"); map.getPane("unitPane").style.zIndex = 300;

  let opacity = 0.9;
  const k = manifest.kerawanan;
  const tileLayers = [];
  let unitLayer = null, unitLevel = null;
  if (k) {
    k.levels.forEach(lv => {
      if (lv.type === "tiles") {
        tileLayers.push(L.tileLayer(DATA_DIR + lv.url, { pane: "kerawananPane", minZoom: lv.minZoom, maxZoom: lv.maxZoom,
          minNativeZoom: lv.minNativeZoom, maxNativeZoom: lv.maxNativeZoom, opacity: opacity, bounds: k.bounds, errorTileUrl: TRANSPARENT_TILE }));
      } else if (lv.type === "geojson") { unitLevel = lv; }
    });
    if (unitLevel) {
      const units = await getJson(DATA_DIR + unitLevel.file);
      unitLayer = L.geoJSON(units, { pane: "unitPane", style: f => Object.assign(unitStyle(k.classes, f.properties), { fillOpacity: opacity }),
        onEachFeature: (f, layer) => layer.bindPopup(unitPopupHtml(f.properties, k)) });
    }
  }
  const lines = {};
  const bfiles = (k && k.boundaries) || {};
  for (const kind of Object.keys(bfiles)) {
    lines[kind] = L.geoJSON(await getJson(DATA_DIR + bfiles[kind]), { style: () => boundaryStyle(kind) });
  }

  const on = id => $(id).checked;
  const toggle = (layer, wanted) => {
    if (!layer) return;
    if (wanted && !map.hasLayer(layer)) map.addLayer(layer);
    if (!wanted && map.hasLayer(layer)) map.removeLayer(layer);
  };
  const syncKerawanan = () => {
    const z = map.getZoom(), want = on("chk-kerawanan");
    tileLayers.forEach(l => toggle(l, want));
    toggle(unitLayer, want && unitLevel && z <= unitLevel.maxZoom);
    $("level").textContent = want && k ? levelLabel(k.levels, z) : "–";
  };
  const syncLines = () => {
    toggle(lines.khg, on("chk-khg")); toggle(lines.admin, on("chk-admin")); toggle(lines.canals, on("chk-canals"));
  };

  // stasiun
  const gj = await getJson(DATA_DIR + manifest.stations.file);
  let mode = "wl";
  const colorFor = f => mode === "wl" ? wlColor(f.properties.wl_last_cm)
    : probColor(f.properties.pred && f.properties.pred.h14 ? f.properties.pred.h14.p_turun10 : null);
  const markers = L.geoJSON(gj, {
    pointToLayer: (f, ll) => L.circleMarker(ll, { pane: "markerPane", radius: 7, weight: 1, color: "#222", fillOpacity: 0.9, fillColor: colorFor(f) }),
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
  });
  const syncStations = () => toggle(markers, on("chk-stations"));

  // lapisan pendukung (relief, jarak, AOA)
  const overlays = manifest.layers.map(l => L.imageOverlay(DATA_DIR + l.file, l.bounds, { opacity: 0.7 }));
  const supportEl = $("support");
  supportEl.innerHTML = manifest.layers.length
    ? manifest.layers.map((l, i) => `<label><input type="checkbox" data-i="${i}"> ${l.title}</label>`).join("<br>")
    : "belum ada";
  let supportLegend = "";
  const renderLegend = () => { $("legend").innerHTML = kerawananLegendHtml(k) + (supportLegend ? "<hr>" + supportLegend : ""); };
  supportEl.addEventListener("change", e => {
    const i = Number(e.target.dataset.i);
    toggle(overlays[i], e.target.checked);
    supportLegend = e.target.checked ? legendHtml(manifest.layers[i]) : "";
    renderLegend();
  });

  ["chk-kerawanan"].forEach(id => $(id).addEventListener("change", syncKerawanan));
  ["chk-khg", "chk-admin", "chk-canals"].forEach(id => $(id).addEventListener("change", syncLines));
  $("chk-stations").addEventListener("change", syncStations);
  map.on("zoomend", syncKerawanan);
  $("opacity").addEventListener("input", e => {
    opacity = Number(e.target.value);
    tileLayers.forEach(l => l.setOpacity(opacity));
    if (unitLayer) unitLayer.setStyle({ fillOpacity: opacity });
    overlays.forEach(o => o.setOpacity(Math.min(opacity, 0.8)));
  });
  document.querySelectorAll("input[name=mode]").forEach(r => r.addEventListener("change", e => {
    mode = e.target.value;
    markers.eachLayer(l => l.setStyle({ fillColor: colorFor(l.feature) }));
  }));

  syncKerawanan(); syncLines(); syncStations(); renderLegend();
  if (k && k.bounds) map.fitBounds(k.bounds);
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { fmt, probColor, wlColor, sparklinePath, validationBadge, predictionTable, legendHtml, startupHint,
                     levelForZoom, levelLabel, classColor, unitStyle, boundaryStyle, unitPopupHtml, kerawananLegendHtml };
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
