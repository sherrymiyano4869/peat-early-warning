"use strict";
const DATA_DIR = "data/";
// Peta dasar: OpenStreetMap standar. Kebijakan tile OSM melarang pemakaian berat tanpa izin dan mewajibkan atribusi yang jelas; untuk lalu lintas besar
// ganti lewat manifest.basemap (tanpa mengubah kode), misalnya ke server tile sendiri atau penyedia berbasis OSM.
const DEFAULT_BASEMAP = { url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png", attribution: "&copy; <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a> contributors", maxZoom: 19 };
const TRANSPARENT_TILE = "data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==";

function fmt(x, d = 1) {
  if (x === null || x === undefined || Number.isNaN(x)) return "–";
  return Number(x).toLocaleString("id-ID", { minimumFractionDigits: d, maximumFractionDigits: d });
}

// Kelas muka air terakhir: ambang acuan -40 cm (titik tengah divergen); biru di atas ambang, cokelat makin gelap makin dalam.
const WL_CLASSES = [
  { min: -40, color: "#2c7bb6", label: "di atas ambang (≥ −40 cm)" },
  { min: -80, color: "#dfc27d", label: "−40 s/d −80 cm" },
  { min: -120, color: "#a6611a", label: "−80 s/d −120 cm" },
  { min: -Infinity, color: "#543005", label: "lebih dalam dari −120 cm" },
];
const NODATA_COLOR = "#9e9e9e";

function wlClass(cm) {
  if (cm === null || cm === undefined || Number.isNaN(cm)) return null;
  return WL_CLASSES.find(c => cm >= c.min) || WL_CLASSES[WL_CLASSES.length - 1];
}

function wlColor(cm) {
  const c = wlClass(cm);
  return c ? c.color : NODATA_COLOR;
}

function isStale(lastDate, dataThrough, days = 3) {
  if (!lastDate || !dataThrough) return true;
  return (Date.parse(dataThrough) - Date.parse(lastDate)) / 86400000 > days;
}

function stationLegendHtml() {
  const rows = WL_CLASSES.map(c => `<span class="dot" style="background:${c.color}"></span>${c.label}`).join("<br>");
  return `<h2>Stasiun SiTMAT: muka air terakhir</h2>${rows}<br><span class="dot" style="background:${NODATA_COLOR}"></span>tanpa data<br>` +
         `<span class="dot stale"></span>berhenti melapor (> 3 hari)`;
}

function trendText(d7) {
  if (d7 === null || d7 === undefined || Number.isNaN(d7)) return "perubahan 7 hari tidak tersedia";
  if (Math.abs(d7) < 2) return "stabil dalam 7 hari terakhir";
  return `${d7 < 0 ? "turun" : "naik"} ${fmt(Math.abs(d7), 0)} cm dalam 7 hari terakhir`;
}

function predictionSentences(pred) {
  const out = ["h7", "h14"].filter(k => pred && pred[k]).map(k => {
    const p = pred[k], dt = Number(p.delta_med);
    const arah = Math.abs(dt) < 2 ? "tetap" : (dt < 0 ? "turun" : "naik");
    return `<li><b>${k.slice(1)} hari ke depan:</b> ${arah} ${fmt(Math.abs(dt), 0)} cm (rentang ${fmt(p.delta_q10, 0)} s/d ${fmt(p.delta_q90, 0)}); ` +
           `peluang turun ≥ 10 cm ${fmt(p.p_turun10 === null ? null : p.p_turun10 * 100, 0)}% ` +
           `<span class="small">(rata-rata di data latih ${fmt(p.p_turun10_basis === null ? null : p.p_turun10_basis * 100, 0)}%)</span></li>`;
  });
  return out.length ? "<ul style=\"margin:4px 0 0 16px;padding:0\">" + out.join("") + "</ul>" : "<div class=\"small\">Belum ada prakiraan untuk stasiun ini.</div>";
}

function stationPopupHtml(p, validation, spark) {
  const c = wlClass(p.wl_last_cm);
  const reliable = validation && validation.available && validation.cap_class >= 1;
  const caveat = reliable ? "" : "<div class=\"small\" style=\"margin:4px 0\">Prakiraan belum dapat diandalkan: model belum terbukti lebih baik daripada tebakan &quot;muka air tetap&quot;. Angka hanya untuk tinjauan.</div>";
  return `<b>${p.name}</b><br><span class="small">${p.id} &middot; ${p.region}</span><br>` +
         `Muka air terakhir (${p.last_date || "–"}): <b>${fmt(p.wl_last_cm, 0)} cm</b>${c ? " · " + c.label : ""}<br>` +
         `${trendText(p.wl_d7_cm)}<br>${spark}` +
         `<div style="margin-top:4px"><b>Prakiraan (prototipe)</b></div>${caveat}${predictionSentences(p.pred)}`;
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
  const c = classColor(classes, props.kelas);
  return { fillColor: c, fillOpacity: 0.85, color: c, weight: 1, opacity: 0.85 };   // tanpa garis tepi abu-abu: hanya isi berwarna
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
  const unmapped = k.unmapped ? `<div class="small" style="margin-top:4px">${k.unmapped}</div>` : "";
  const scheme = k.class_scheme ? `<div class="small" style="margin-top:2px">${k.class_scheme}</div>` : "";
  const hs = k.hillshade ? `<div class="small" style="margin-top:4px">${k.hillshade.note}</div>` : "";
  return `<h2>${k.title} (indeks relatif)</h2>${cls}<div class="small" style="margin-top:4px">${mode}</div>${scheme}${unmapped}` +
         `<h2>Kepercayaan peta</h2>${conf}<div class="small">Arsiran berarti jauh dari stasiun atau kondisi lahan berbeda dari stasiun.</div>${hs}` +
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
  const baseOpts = b => ({ maxZoom: b.maxZoom || 19, attribution: b.attribution, className: "basemap-muted" });  // kelas CSS meredam warna agar peta dasar tidak mengalahkan tema
  let baseLayer = L.tileLayer(DEFAULT_BASEMAP.url, baseOpts(DEFAULT_BASEMAP)).addTo(map);
  L.control.scale({ metric: true, imperial: false }).addTo(map);
  if (location.protocol === "file:") throw new Error("file-protocol");
  const manifest = await getJson(DATA_DIR + "manifest.json");
  if (manifest.basemap && manifest.basemap.url && manifest.basemap.url !== DEFAULT_BASEMAP.url) {
    map.removeLayer(baseLayer);
    baseLayer = L.tileLayer(manifest.basemap.url, baseOpts(manifest.basemap)).addTo(map);
  }
  const $ = id => document.getElementById(id);
  $("title").textContent = manifest.title;
  $("meta").innerHTML =
    `Versi ${manifest.version} &middot; dibuat ${manifest.generated_at}<br>Data sampai ${manifest.data_through || "–"} &middot; tanggal terbit prediksi ${manifest.issue_date || "–"}`;
  const badge = validationBadge(manifest.validation);
  $("badge").className = "badge " + badge.cls;
  $("badge").textContent = badge.text;
  $("attrib").innerHTML = "<p>" + manifest.attribution.join("</p><p>") + "</p><p><b>" + manifest.disclaimer + "</b></p>";
  map.setView(manifest.center, 11);
  map.createPane("hillshadePane"); map.getPane("hillshadePane").style.zIndex = 240;
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
  const hs = k && k.hillshade ? L.tileLayer(DATA_DIR + k.hillshade.url, { pane: "hillshadePane", minZoom: k.hillshade.minZoom, maxZoom: k.hillshade.maxZoom,
    minNativeZoom: k.hillshade.minNativeZoom, maxNativeZoom: k.hillshade.maxNativeZoom, opacity: 0.9, bounds: k.bounds, errorTileUrl: TRANSPARENT_TILE }) : null;
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
  const syncHillshade = () => toggle(hs, on("chk-hillshade"));
  const syncLines = () => {
    toggle(lines.khg, on("chk-khg")); toggle(lines.admin, on("chk-admin")); toggle(lines.canals, on("chk-canals"));
  };

  // stasiun
  const gj = await getJson(DATA_DIR + manifest.stations.file);
  const styleFor = f => {
    const p = f.properties, stale = isStale(p.last_date, manifest.data_through);
    return stale ? { fillColor: NODATA_COLOR, fillOpacity: 0.15, color: "#555", weight: 1.5, dashArray: "3 3", className: "station-marker" }
                 : { fillColor: wlColor(p.wl_last_cm), fillOpacity: 1, color: "#ffffff", weight: 2, className: "station-marker" };   // lingkaran putih + bayangan: terbaca di atas warna kerawanan apa pun
  };
  const markers = L.geoJSON(gj, {
    pointToLayer: (f, ll) => L.circleMarker(ll, Object.assign({ pane: "markerPane", radius: 7 }, styleFor(f))),
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
        layer.setPopupContent(stationPopupHtml(p, manifest.validation, spark));
      });
    }
  });
  const syncStations = () => toggle(markers, on("chk-stations"));

  // lapisan pendukung (relief, jarak, AOA)
  const overlays = manifest.layers.map(l => L.imageOverlay(DATA_DIR + l.file, l.bounds, { opacity: 0.7 }));
  const supportEl = $("support");
  supportEl.innerHTML = manifest.layers.length
    ? manifest.layers.map((l, i) => `<label><input type="checkbox" data-i="${i}"> ${l.title}</label>`).join("<br>")
    : "";
  let supportLegend = "";
  const renderLegend = () => {
    $("legendbox").innerHTML = kerawananLegendHtml(k) + stationLegendHtml();
    $("legend").innerHTML = supportLegend;
  };
  const ss = $("support-sect"); if (!manifest.layers.length && ss && ss.style) ss.style.display = "none";
  supportEl.addEventListener("change", e => {
    const i = Number(e.target.dataset.i);
    toggle(overlays[i], e.target.checked);
    supportLegend = e.target.checked ? legendHtml(manifest.layers[i]) : "";
    renderLegend();
  });

  ["chk-kerawanan"].forEach(id => $(id).addEventListener("change", syncKerawanan));
  $("chk-hillshade").addEventListener("change", syncHillshade);
  ["chk-khg", "chk-admin", "chk-canals"].forEach(id => $(id).addEventListener("change", syncLines));
  $("chk-stations").addEventListener("change", syncStations);
  map.on("zoomend", syncKerawanan);
  $("opacity").addEventListener("input", e => {
    opacity = Number(e.target.value);
    tileLayers.forEach(l => l.setOpacity(opacity));
    if (unitLayer) unitLayer.setStyle({ fillOpacity: opacity });
    overlays.forEach(o => o.setOpacity(Math.min(opacity, 0.8)));
  });

  syncKerawanan(); syncHillshade(); syncLines(); syncStations(); renderLegend();
  if (k && k.bounds) map.fitBounds(k.bounds);
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { fmt, wlColor, wlClass, isStale, stationLegendHtml, trendText, predictionSentences, stationPopupHtml, sparklinePath, validationBadge, predictionTable, legendHtml, startupHint,
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
