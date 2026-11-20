"use strict";
const DATA_DIR = "data/";
const PAGE = (typeof window !== "undefined" && window.PAGE) || "monitoring";   // "monitoring" atau "prediction" (diatur oleh HTML)
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

function stationPopupHtml(p, validation, spark, withForecast = true) {
  const c = wlClass(p.wl_last_cm);
  const reliable = validation && validation.available && validation.cap_class >= 1;
  const caveat = reliable ? "" : "<div class=\"small\" style=\"margin:4px 0\">Prakiraan belum dapat diandalkan: model belum terbukti lebih baik daripada tebakan &quot;muka air tetap&quot;. Angka hanya untuk tinjauan.</div>";
  return `<b>${p.name}</b><br><span class="small">${p.id} &middot; ${p.region}</span><br>` +
         `Muka air terakhir (${p.last_date || "–"}): <b>${fmt(p.wl_last_cm, 0)} cm</b>${c ? " · " + c.label : ""}<br>` +
         `${trendText(p.wl_d7_cm)}<br>${spark}` +
         (withForecast ? `<div style="margin-top:4px"><b>Prakiraan muka air (prototipe)</b></div>${caveat}${predictionSentences(p.pred)}` : "");
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
  if (kind === "khg") return { color: "#4A1F14", weight: 1.6, dashArray: "6 4", fill: false };
  if (kind === "admin") return { color: "#8a8a8a", weight: 0.9, fill: false };
  return { color: "#3E7CA6", weight: 0.7, opacity: 0.85 };   // kanal: garis biru tipis, bukan peta panas
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
  const conf = `<span class="swatch" style="background:#B5432F"></span>pekat: kepercayaan tinggi<br>` +
               `<span class="swatch" style="background:#B5432F;opacity:.7"></span>agak transparan: sedang<br>` +
               `<span class="swatch hatch" style="background-color:#D77A3C;opacity:.6"></span>transparan dan diarsir: rendah`;
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


// ---- titik api teramati (monitoring) ------------------------------------------
function ageDays(dateStr, refStr) {
  return Math.round((Date.parse(refStr) - Date.parse(dateStr)) / 86400000);
}

const HOT_AGE = [
  { max: 0, color: "#B5432F", label: "hari ini" },
  { max: 3, color: "#D77A3C", label: "1–3 hari lalu" },
  { max: 7, color: "#F2D68A", label: "4–7 hari lalu" },
];

function hotspotColor(age) {
  const c = HOT_AGE.find(a => age <= a.max);
  return c ? c.color : "#bdbdbd";
}

function hotspotStyle(p, refDate) {
  const age = ageDays(p.date, refDate);
  const r = Math.min(9, Math.max(3.5, 3 + Math.log10(1 + Math.max(p.frp || 0, 0)) * 3));
  return { radius: r, fillColor: hotspotColor(age), fillOpacity: 0.9, color: "#222", weight: 1 };
}

function hotspotPopupHtml(p) {
  const conf = ["rendah", "nominal", "tinggi"][p.conf] || "–";
  return `<b>Titik api VIIRS</b><br>Tanggal (WIB): ${p.date} · ${p.dn === "N" ? "malam" : "siang"}<br>` +
         `Keyakinan deteksi: ${conf} · FRP: ${fmt(p.frp, 1)} MW<br><span class="small">Pengamatan satelit 375 m; tidak terdeteksi bukan berarti tidak ada api (awan dan asap menutup).</span>`;
}

function hotspotLegendHtml(h) {
  const rows = HOT_AGE.map(a => `<span class="dot" style="background:${a.color}"></span>${a.label}`).join("<br>");
  return `<h2>Titik api teramati (VIIRS)</h2>${rows}<div class="small">Ukuran lingkaran = daya radiasi api (FRP). ${h && h.note ? h.note : ""}</div>`;
}

// ---- peluang titik api (prediksi) ---------------------------------------------
const FIRE_CLASSES = [
  { min: 0.30, color: "#B5432F", label: "peluang ≥ 30%", short: "≥ 30%" },
  { min: 0.10, color: "#D77A3C", label: "10–30%", short: "10–30%" },
  { min: 0.03, color: "#EBB46A", label: "3–10%", short: "3–10%" },
  { min: 0, color: "#F2D68A", label: "di bawah 3% (tetap 5% teratas)", short: "< 3%" },
];

function fireClass(p) {
  return FIRE_CLASSES.find(c => p >= c.min) || FIRE_CLASSES[FIRE_CLASSES.length - 1];
}

function fireCellStyle(props, fire, opacity = 0.85, key) {
  const c = fireClass(props[key || fire.primary_key || "p1"]).color;
  return { fillColor: c, fillOpacity: opacity, color: c, weight: 1, opacity: opacity };   // tanpa garis tepi abu-abu
}

function firePopupHtml(p, fire) {
  const pct = x => (x === null || x === undefined ? "–" : fmt(x * 100, x < 0.1 ? 1 : 0) + "%");
  const caveat = fire && fire.cap_class >= 1 ? "" :
    "<div class=\"small\" style=\"margin-top:4px\">Belum terbukti mengalahkan pembanding sederhana pada uji; perlakukan sebagai petunjuk.</div>";
  return `<b>Sel 1 km · peringkat ${p.rank}</b><br>Peluang ada titik api besok: <b>${pct(p.p1)}</b> ` +
         `<span class="small">(rata-rata sel ini pada bulan ini ${pct(p.p1_klim)})</span><br>` +
         `Dalam 3 hari: <b>${pct(p.p3)}</b> <span class="small">(rata-rata ${pct(p.p3_klim)})</span>` +
         `<div class="small" style="margin-top:4px">Peluang per sel, bukan titik pasti. Tanggal terbit ${fire ? fire.issue_date : "–"}.</div>${caveat}`;
}

function fireLegendHtml(fire) {
  if (!fire) return "";
  const rows = FIRE_CLASSES.map(c => `<span class="swatch" style="background:${c.color}"></span>${c.label}`).join("<br>");
  return `<h2>Peluang ada titik api besok</h2>${rows}<div class="small">Hanya ${fmt(fire.top_fraction * 100, 0)}% sel teratas yang digambar. ` +
         `Peluang dikalibrasi; harapan jumlah sel berapi besok ${fmt(fire.expected_cells_h1, 1)} dari ${fmt(fire.n_cells, 0)} sel.</div>`;
}

function fireBadge(fire) {
  if (!fire || !fire.metrics) return { cls: "warn", text: "Model titik api belum dijalankan." };
  const m = fire.metrics;
  if (!fire.skill_ok) {
    return { cls: "bad", text: `Model titik api belum terbukti mengalahkan klimatologi dan persistensi pada uji (PR-AUC ${fmt(m.pr_auc_model, 2)} lawan ${fmt(m.pr_auc_klim, 2)} dan ${fmt(m.pr_auc_persist, 2)}). Kepercayaan: rendah.` };
  }
  return { cls: "warn", text: `Uji retrospektif (${m.periode_uji}, bulan api): PR-AUC model ${fmt(m.pr_auc_model, 2)} lawan klimatologi ${fmt(m.pr_auc_klim, 2)} dan persistensi ${fmt(m.pr_auc_persist, 2)}; ` +
                              `skill Brier ${fmt(m.skill_brier, 2)}. Belum diuji prospektif pada arsip. Kepercayaan: sedang.` };
}

// ---- prakiraan pengeringan per sel (prediksi) ----------------------------------
const DRY_CLASSES = [
  { min: 0.60, color: "#2C6A8E", label: "≥ 60%", short: "≥ 60%" },
  { min: 0.45, color: "#5B93B3", label: "45–60%", short: "45–60%" },
  { min: 0.30, color: "#93BBD0", label: "30–45%", short: "30–45%" },
  { min: 0.15, color: "#C9DCE6", label: "15–30%", short: "15–30%" },
  { min: 0, color: "#EEF3F6", label: "di bawah 15%", short: "< 15%" },
];

function dryClass(p) {
  return DRY_CLASSES.find(c => p >= c.min) || DRY_CLASSES[DRY_CLASSES.length - 1];
}

function dryCellStyle(props, dry, opacity = 0.85, key = "p14") {
  const o = dry && dry.cap_class >= 1 ? opacity : opacity * 0.55;     // kepercayaan rendah: lebih transparan
  const c = dryClass(props[key]).color;
  return { fillColor: c, fillOpacity: o, color: c, weight: 1, opacity: o };
}

function dryPopupHtml(p, dry) {
  const pct = x => fmt(x * 100, 0) + "%";
  const signed = x => (x > 0 ? "+" : "") + fmt(x, 0);
  const caveat = dry && dry.cap_class >= 1 ? "" :
    "<div class=\"small\" style=\"margin-top:4px\">Belum terbukti lebih baik daripada &quot;muka air tetap&quot; pada stasiun baru dan tanggal baru; perlakukan sebagai petunjuk.</div>";
  return `<b>Sel 1 km · prakiraan pengeringan</b><br>14 hari: peluang muka air turun ≥ 10 cm <b>${pct(p.p14)}</b>; perubahan median ${signed(p.d14)} cm ` +
         `<span class="small">(rentang ${signed(p.q10_14)} s/d ${signed(p.q90_14)})</span><br>7 hari: peluang <b>${pct(p.p7)}</b>; median ${signed(p.d7)} cm` +
         `<div class="small" style="margin-top:4px">Dilatih di stasiun SiTMAT tanpa muka air saat ini sebagai masukan; sel jauh dari klaster stasiun adalah ekstrapolasi. Terbit ${dry ? dry.issue_date : "–"}.</div>${caveat}`;
}

function dryLegendHtml(dry) {
  if (!dry) return "";
  const rows = DRY_CLASSES.map(c => `<span class="swatch" style="background:${c.color}"></span>${c.label}`).join("<br>");
  return `<h2>Peluang muka air turun ≥ 10 cm dalam 14 hari</h2>${rows}<div class="small">Perkiraan model dari stasiun SiTMAT, per sel 1 km` +
         `${dry.cap_class >= 1 ? "" : "; warna dipucatkan karena belum terbukti mengalahkan pembanding"}.</div>`;
}

function dryBadge(dry) {
  if (!dry || !dry.metrics) return { cls: "warn", text: "Model pengeringan per sel belum dijalankan." };
  const m = dry.metrics.h14 || {};
  if (!dry.skill_ok) {
    return { cls: "bad", text: `Pengeringan per sel belum terbukti pada stasiun baru dan tanggal baru (skill MAE ${fmt(m.skill_mae, 2)}, cakupan q10–q90 ${fmt((m.cakupan_q10_q90 || 0) * 100, 0)}%, ${dry.n_stasiun} stasiun). Kepercayaan: rendah.` };
  }
  return { cls: "warn", text: `Uji ruang-waktu (${dry.n_stasiun} stasiun): skill MAE ${fmt(m.skill_mae, 2)} lawan "tetap", cakupan q10–q90 ${fmt(m.cakupan_q10_q90 * 100, 0)}%. Belum diuji di luar klaster stasiun. Kepercayaan: sedang.` };
}

// ---- ringkasan dan faktor penyusun ------------------------------------------
function stationSummary(features) {
  const out = { total: features.length, stale: 0, nodata: 0, byClass: WL_CLASSES.map(c => ({ label: c.label, color: c.color, n: 0 })) };
  features.forEach(f => {
    const c = wlClass(f.properties.wl_last_cm);
    if (!c) { out.nodata++; return; }
    out.byClass[WL_CLASSES.indexOf(c)].n++;
  });
  return out;
}

function monitoringSummaryHtml(stations, hot, manifest) {
  const s = stationSummary(stations);
  const rows = s.byClass.map(c => `<span class="dot" style="background:${c.color}"></span>${c.label}: <b>${c.n}</b>`).join("<br>");
  let hotTxt = "<span class=\"small\">Titik api teramati belum dimuat (jalankan 12, 13, lalu 09).</span>";
  if (hot) {
    const d0 = hot.features.filter(f => ageDays(f.properties.date, hot.date_max) <= 0).length;
    hotTxt = `Titik api VIIRS: <b>${d0}</b> hari ini · <b>${hot.features.length}</b> dalam 7 hari (sampai ${hot.date_max})`;
  }
  return `<b>Ringkasan kondisi kini</b><br>Stasiun SiTMAT (${s.total}), muka air terakhir:<br>${rows}${s.nodata ? `<br><span class="dot" style="background:${NODATA_COLOR}"></span>tanpa data: <b>${s.nodata}</b>` : ""}<br>${hotTxt}`;
}

function predictionSummaryHtml(fire, dry) {
  const dryTxt = dry ? `<br>Pengeringan 14 hari: peluang rata-rata <b>${fmt(dry.p14_rata2 * 100, 0)}%</b> per sel (${fmt(dry.n_cells, 0)} sel)` : "";
  if (!fire) return "<b>Ringkasan prakiraan</b><br><span class=\"small\">Belum ada prediksi titik api (jalankan 13 dan 14, lalu 09).</span>" + dryTxt;
  return `<b>Ringkasan prakiraan</b> <span class="small">terbit ${fire.issue_date}</span><br>Harapan sel 1 km berapi besok: <b>${fmt(fire.expected_cells_h1, 1)}</b> dari ${fmt(fire.n_cells, 0)}<br>` +
         `Sel teratas digambar: <b>${fire.n_top}</b> (${fmt(fire.top_fraction * 100, 0)}%)${dryTxt}`;
}

function driversHtml(drivers, title) {
  if (!drivers || !drivers.length) return "";
  const icon = s => s === "tersedia" ? "●" : (s === "sebagian" ? "◐" : "○");
  const rows = drivers.map(d => `<div><span title="${d.status}">${icon(d.status)}</span> <b>${d.title}</b> <span class="small">· ${d.detail || d.status}</span></div>`).join("");
  return `<b>${title}</b><div class="small" style="margin:2px 0">● tersedia · ◐ sebagian · ○ belum tersedia</div>${rows}`;
}

function monitoringBadge(manifest) {
  const k = manifest.kerawanan;
  if (!k) return { cls: "warn", text: "Peta kerentanan belum dibuat (jalankan 07, 08, 10, lalu 09)." };
  if (k.mode === "struktural") {
    return { cls: "warn", text: "Indeks kondisi kini baru memuat kerentanan struktural (kanal dan relief). Hujan, kelembapan tanah, dan muka air belum disertakan per sel." };
  }
  return { cls: "ok", text: "Indeks kondisi kini memuat kerentanan struktural dan tekanan dinamis. Kalibrasi terhadap stasiun SiTMAT belum diuji." };
}

// ---- bantu tampilan halaman Monitoring dan Prediksi ---------------------------------
const MONTHS_ID = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
const CONF_LABEL = ["rendah", "sedang", "tinggi"];
const esc = t => String(t ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const pctTxt = x => (x === null || x === undefined || Number.isNaN(x) ? "–" : fmt(x * 100, x < 0.1 ? 1 : 0) + "%");
const cellKey = f => String(f.properties.cell_id ?? f.id ?? f.geometry.coordinates[0][0].join(","));

function tglId(iso) {
  if (!iso) return "–";
  const d = new Date(String(iso).slice(0, 10) + "T00:00:00Z");
  return Number.isNaN(d.getTime()) ? "–" : `${d.getUTCDate()} ${MONTHS_ID[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

// Stasiun di bawah -40 cm sekarang dan 7 hari lalu (nilai lalu = terakhir - wl_d7_cm); hanya stasiun yang punya keduanya
function stationTrend(features) {
  let now = 0, prev = 0, n = 0;
  features.forEach(f => {
    const p = f.properties;
    if (p.wl_last_cm === null || p.wl_last_cm === undefined || p.wl_d7_cm === null || p.wl_d7_cm === undefined) return;
    n++;
    if (p.wl_last_cm < -40) now++;
    if (p.wl_last_cm - p.wl_d7_cm < -40) prev++;
  });
  return { now, prev, n };
}

// Tugas terbuka = belum ada hasil dari Kobo DAN belum ditandai diperiksa atau tidak terjangkau oleh petugas
function openTasks(tasks) {
  const done = f => f.properties.hasil !== "belum" || ["diperiksa", "tidak_terjangkau"].includes(f.properties.status_lapangan);
  return { total: tasks.length, open: tasks.filter(f => !done(f)).length };
}

function kpiHtml(stations, hot, manifest, tasks) {
  const s = stationSummary(stations), withData = s.total - s.nodata, below = withData - s.byClass[0].n, tr = stationTrend(stations);
  const card = (label, value, sub) => `<div class="kpi"><span>${label}</span><b>${value}</b><small>${sub}</small></div>`;
  const fire = manifest.fire;
  const diff = tr.n === withData && withData > 0 ? tr.now - tr.prev : null;
  return [
    hot ? card("Titik api VIIRS, 7 hari", hot.features.length, `${hot.features.filter(f => ageDays(f.properties.date, hot.date_max) <= 0).length} hari ini`)
        : card("Titik api VIIRS, 7 hari", "–", "belum dimuat"),
    fire ? card("Harapan sel berapi besok", fmt(fire.expected_cells_h1, 1), `dari ${fmt(fire.n_cells, 0)} sel · kepercayaan ${CONF_LABEL[Math.min(2, fire.cap_class || 0)]}`)
         : card("Harapan sel berapi besok", "–", "model belum dijalankan"),
    card("Stasiun di bawah −40 cm", `${below}/${withData}`,
         diff === null ? (s.nodata ? `${s.nodata} tanpa data` : "perubahan 7 hari tidak lengkap") : (diff === 0 ? "sama dengan 7 hari lalu" : `${diff > 0 ? "+" : ""}${diff} dibanding 7 hari lalu`)),
    tasks ? card("Tugas pemeriksaan terbuka", openTasks(tasks).open, `dari ${openTasks(tasks).total} tugas`) : card("Tugas pemeriksaan terbuka", "–", "belum ada data tugas"),
  ].join("");
}

function statusText(stations, hot) {
  const s = stationSummary(stations), withData = s.total - s.nodata, below = withData - s.byClass[0].n;
  const h = hot ? `${hot.features.length} titik api VIIRS dalam 7 hari terakhir (sampai ${tglId(hot.date_max)}). ` : "";
  return `${h}Muka air di ${below} dari ${withData} stasiun SiTMAT berada di bawah −40 cm pada pembacaan terakhir.`;
}

function compactLegendHtml(k, hot) {
  const row = (bg, label, cls = "") => `<div class="lg-row"><i class="${cls}" style="background:${bg}"></i>${label}</div>`;
  const cls = k ? "<b>Kerentanan relatif</b>" + [...k.classes].reverse().map(c => row(c.color, c.label)).join("") : "";
  const hotRow = hot ? row("radial-gradient(circle, #F2D68A 0%, #D77A3C 45%, #4A1F14 100%)", "Titik api, 7 hari", "round") : "";
  const stn = row(WL_CLASSES[0].color, "Stasiun di atas ambang (≥ −40 cm)", "round") + row(WL_CLASSES[2].color, "Stasiun di bawah −40 cm", "round");
  return cls + (cls ? '<div class="lg-sep"></div>' : "") + hotRow + stn;
}

function sparklineSvg(values, w = 140, h = 28, thr = -40) {
  const pts = values.map((x, i) => [i, x]).filter(p => p[1] !== null && p[1] !== undefined && !Number.isNaN(p[1]));
  if (pts.length < 2) return "";
  const ys = pts.map(p => p[1]), lo = Math.min(...ys, thr), hi = Math.max(...ys, thr), span = hi - lo || 1, pad = 2;
  const y = v => (h - pad - ((v - lo) / span) * (h - 2 * pad)).toFixed(1);
  const x = i => (pad + (i / (values.length - 1)) * (w - 2 * pad)).toFixed(1);
  const d = pts.map((p, j) => `${j ? "L" : "M"}${x(p[0])} ${y(p[1])}`).join("");
  return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true"><line x1="0" x2="${w}" y1="${y(thr)}" y2="${y(thr)}" stroke="#D77A3C" stroke-dasharray="3 3" stroke-width="1" vector-effect="non-scaling-stroke"/>` +
         `<path d="${d}" fill="none" stroke="#93351F" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>`;
}

function stationRowHtml(f) {
  const p = f.properties, low = p.wl_last_cm !== null && p.wl_last_cm !== undefined && p.wl_last_cm < -40;
  return `<button type="button" class="stn" data-sid="${esc(p.id)}" title="${esc(p.name)} · ${esc(p.region)}"><span class="nm">${esc(p.name || p.id)}</span><span class="spark"></span>` +
         `<span class="v${low ? " low" : ""}">${p.wl_last_cm === null || p.wl_last_cm === undefined ? "–" : fmt(p.wl_last_cm, 0) + " cm"}</span></button>`;
}

function stationRowsHtml(features, shown = 8) {
  const sorted = [...features].sort((a, b) => (a.properties.wl_last_cm ?? Infinity) - (b.properties.wl_last_cm ?? Infinity));
  const head = sorted.slice(0, shown).map(stationRowHtml).join(""), rest = sorted.slice(shown);
  return head + (rest.length ? `<details class="about"><summary>Semua stasiun (${sorted.length})</summary><div>${rest.map(stationRowHtml).join("")}</div></details>` : "");
}

function priorityHtml(rows, key, subFn) {
  if (!rows.length) return "<div class=\"note\">Belum ada prediksi (jalankan 13 dan 14, lalu 09).</div>";
  return rows.map((f, i) => {
    const p = f.properties, v = p[key];
    return `<button type="button" class="prio" data-cell="${esc(cellKey(f))}" aria-pressed="false"><span class="top"><span class="pt">${i + 1}. Sel ${esc(cellKey(f))}</span><span class="pv">${pctTxt(v)}</span></span>` +
           `<span class="meter"><div style="width:${Math.min(100, Math.max(0, v * 100)).toFixed(0)}%"></div></span><span class="sub">${subFn(p)}</span></button>`;
  }).join("");
}

function reportsHtml(events) {
  const rows = events.filter(f => f.properties.sumber !== "satelit").sort((a, b) => String(b.properties.date).localeCompare(String(a.properties.date)) || String(a.properties.tingkat).localeCompare(String(b.properties.tingkat))).slice(0, 6);
  if (!rows.length) return "<div class=\"note\">Belum ada laporan lapangan pada rentang data.</div>";
  return rows.map(f => {
    const p = f.properties;
    const title = p.status === "kejadian" ? (p.sumber === "keduanya" ? "Kejadian: laporan cocok dengan VIIRS" : "Kejadian dilaporkan") : (p.status === "nihil" ? "Diperiksa: tidak ada kejadian" : "Kunjungan tanpa kejadian");
    return `<div class="rep"><span class="grade ${esc(p.tingkat)}">${esc(p.tingkat || "–")}</span><div><div class="t">${title}</div><div class="m">Sel ${esc(p.cell_id)} · ${tglId(p.date)}</div></div></div>`;
  }).join("");
}

function evidenceHtml(items) {
  const word = { bad: "belum terbukti", warn: "bukti terbatas", ok: "teruji" };
  return items.map(i => `<details class="evi ${i.badge.cls}"><summary>${i.label}: ${word[i.badge.cls] || "–"}</summary><div>${esc(i.badge.text)}</div></details>`).join("");
}

function cellPanelHtml(c) {
  const { theme, id, f, other, fire, dry, nTop } = c;
  const cap = theme === "fire" ? (fire ? fire.cap_class : 0) : (dry ? dry.cap_class : 0), conf = Math.min(2, cap || 0);
  const bars = [0, 1, 2].map(i => `<i class="${i <= conf ? "on" : ""}"></i>`).join("");
  const p = f ? f.properties : null;
  let head, tiles, sub;
  if (theme === "fire") {
    sub = p ? `peringkat ${p.rank} dari ${nTop} sel teratas · terbit ${tglId(fire.issue_date)}` : `tidak termasuk sel teratas yang diekspor (peluang sel ini tidak tersedia)`;
    tiles = `<div class="tile"><span>Peluang titik api besok</span><b>${p ? pctTxt(p.p1) : "–"}</b><small>${p ? "rata-rata sel ini bulan ini " + pctTxt(p.p1_klim) : ""}</small></div>` +
            `<div class="tile"><span>Dalam 3 hari</span><b>${p ? pctTxt(p.p3) : "–"}</b><small>${p ? "rata-rata " + pctTxt(p.p3_klim) : ""}</small></div>`;
  } else {
    const s = v => (v > 0 ? "+" : "") + fmt(v, 0);
    sub = p ? `prakiraan pengeringan · terbit ${tglId(dry.issue_date)}` : "sel ini tidak dinilai model pengeringan";
    tiles = `<div class="tile"><span>Peluang muka air turun ≥ 10 cm, 7 hari</span><b>${p ? pctTxt(p.p7) : "–"}</b><small>${p ? "median " + s(p.d7) + " cm" : ""}</small></div>` +
            `<div class="tile"><span>Peluang turun ≥ 10 cm, 14 hari</span><b>${p ? pctTxt(p.p14) : "–"}</b><small>${p ? "median " + s(p.d14) + " cm (rentang " + s(p.q10_14) + " s/d " + s(p.q90_14) + ")" : ""}</small></div>`;
  }
  const o = other ? other.properties : null;
  const otherTxt = o ? (theme === "fire" ? `Pengeringan 14 hari untuk sel ini: <b>${pctTxt(o.p14)}</b>` : `Peluang titik api besok untuk sel ini: <b>${pctTxt(o.p1)}</b>`) : "";
  const drivers = p && Array.isArray(p.drivers) && p.drivers.length
    ? `<div class="drv-wrap"><b>Mengapa sel ini tinggi?</b>${p.drivers.map(d => `<div class="drv"><div class="l"><span>${esc(d.label)}</span><span>${esc(d.value)}</span></div><div class="meter"><div style="width:${Math.min(100, Math.max(0, d.w))}%"></div></div></div>`).join("")}</div>`
    : "<div class=\"note\">Faktor pendorong per sel belum diekspor oleh model (perlu keluaran faktor dari skrip 14 dan 15), jadi tidak ditampilkan.</div>";
  return `<div><div class="cell-kicker">SEL TERPILIH</div><h2 class="cell-id">Sel ${esc(id)}</h2><div class="note">${sub}</div></div><div class="tiles">${tiles}</div>` +
         `<div class="conf"><b>Kepercayaan model:</b><span class="bars" aria-hidden="true">${bars}</span><span>${CONF_LABEL[conf]} (dari uji model, bukan per sel)</span></div>` +
         (otherTxt ? `<div class="note">${otherTxt}</div>` : "") + drivers;
}

function trustHtml(c) {
  const { theme, fire, dry, scores } = c;
  let c1;
  if (theme === "fire") {
    const m = fire && fire.metrics, rows = m ? [["Model", m.pr_auc_model], ["Klimatologi", m.pr_auc_klim], ["Persistensi", m.pr_auc_persist]] : [];
    const mx = Math.max(...rows.map(r => r[1] || 0), 1e-9);
    c1 = `<h3>Titik api besok: model lawan pembanding</h3>` + (rows.length ? rows.map(([n, v], i) => `<div class="hbar"><div class="l"><span>${n}</span><strong>PR-AUC ${fmt(v, 2)}</strong></div><div class="b${i ? " alt" : ""}"><div style="width:${((v || 0) / mx * 100).toFixed(0)}%"></div></div></div>`).join("") +
      `<div class="note">Uji retrospektif ${esc(m.periode_uji)}; skill Brier ${fmt(m.skill_brier, 2)}. Belum diuji prospektif pada arsip.</div>` : "<div class=\"note\">Metrik belum diekspor (jalankan 14, lalu 09).</div>");
  } else {
    const m = dry && dry.metrics;
    c1 = `<h3>Pengeringan per sel: uji ruang-waktu</h3>` + (m ? ["h7", "h14"].filter(h => m[h]).map(h => `<div>${h.slice(1)} hari: skill MAE <b>${fmt(m[h].skill_mae, 2)}</b> lawan "tetap"; cakupan q10–q90 <b>${fmt((m[h].cakupan_q10_q90 || 0) * 100, 0)}%</b> (target 80%); ${fmt(m[h].n_uji, 0)} uji</div>`).join("") : "<div class=\"note\">Metrik belum diekspor (jalankan 15, lalu 09).</div>");
  }
  const sc = scores && scores.scores, a = sc && sc.tugas_pemeriksaan && sc.tugas_pemeriksaan.per_alasan;
  let c2 = "<h3>Tugas teratas lawan acak</h3>";
  if (a && a.teratas && a.acak) {
    const pc = (k, n) => (a[k].diperiksa ? a[k].kejadian / a[k].diperiksa : 0) * 100;
    c2 += [["teratas", "Sel prioritas model"], ["acak", "Sel acak"]].map(([k, n], i) => `<div class="hbar"><div class="l"><span>${n}</span><strong>${fmt(pc(k), 0)}% (${a[k].kejadian} dari ${a[k].diperiksa})</strong></div><div class="b${i ? " alt" : ""}"><div style="width:${pc(k).toFixed(0)}%"></div></div></div>`).join("") +
          `<div class="note">Bagian sel yang kejadiannya ditemukan saat diperiksa (skrip 18). Jumlah kecil: baca sebagai petunjuk.${scores.tiruan ? " <b>DATA TIRUAN.</b>" : ""}</div>`;
  } else {
    c2 += "<div class=\"note\">Belum ada penilaian prospektif. Jalankan 18, lalu 20 dan 21.</div>";
  }
  const h1 = sc && sc.titik_api && sc.titik_api.h1, li = [];
  if (fire && fire.metrics && fire.metrics.periode_uji) li.push(`Uji retrospektif titik api: ${esc(fire.metrics.periode_uji)}`);
  if (fire && fire.metrics && fire.metrics.pr_auc_klim !== undefined) li.push("Dibandingkan dengan pembanding sederhana: klimatologi dan persistensi");
  if (dry && dry.n_stasiun) li.push(`Pengeringan: uji ruang-waktu pada ${dry.n_stasiun} stasiun`);
  li.push(h1 ? `Prediksi diarsipkan sebelum kejadian, lalu dinilai: lolos uji prospektif <b>${h1.lolos_prospektif ? "ya" : "belum"}</b>` : "Penilaian prospektif (arsip prediksi lawan kejadian): belum ada");
  return `<div class="sub-card">${c1}</div><div class="sub-card">${c2}</div><div class="sub-card"><h3>Cara pengujian</h3><ul>${li.map(x => `<li>${x}</li>`).join("")}</ul></div>`;
}

async function main() {
  // Dari file:// peramban tidak mengirim Referer, dan server tile OSM menolak (403 "Access blocked"). Jangan minta tile sama sekali; tampilkan petunjuk.
  if (location.protocol === "file:") throw new Error("file-protocol");
  const $ = id => document.getElementById(id);
  const isPred = PAGE === "prediction";
  const map = L.map("map").setView([-1.3, 104.0], 8);
  // referrerPolicy "origin": pastikan asal halaman (mis. http://localhost:8000) ikut terkirim sebagai Referer, sesuai kebijakan tile OSM
  const baseOpts = b => ({ maxZoom: b.maxZoom || 19, attribution: b.attribution, className: "basemap-muted", referrerPolicy: "origin" });  // kelas CSS meredam warna agar peta dasar tidak mengalahkan tema
  let baseLayer = L.tileLayer(DEFAULT_BASEMAP.url, baseOpts(DEFAULT_BASEMAP)).addTo(map);
  L.control.scale({ metric: true, imperial: false }).addTo(map);
  const manifest = await getJson(DATA_DIR + "manifest.json");
  if (manifest.basemap && manifest.basemap.url && manifest.basemap.url !== DEFAULT_BASEMAP.url) {
    map.removeLayer(baseLayer);
    baseLayer = L.tileLayer(manifest.basemap.url, baseOpts(manifest.basemap)).addTo(map);
  }
  if ($("meta")) $("meta").textContent = `Versi ${manifest.version} · dibuat ${manifest.generated_at} · data sampai ${manifest.data_through || "–"} · tanggal terbit prediksi ${manifest.issue_date || "–"}`;
  $("attrib").innerHTML = "<p>" + manifest.attribution.join("</p><p>") + "</p><p><b>" + manifest.disclaimer + "</b></p>";
  map.setView(manifest.center, 11);
  map.createPane("hillshadePane"); map.getPane("hillshadePane").style.zIndex = 240;
  map.createPane("kerawananPane"); map.getPane("kerawananPane").style.zIndex = 250;
  map.createPane("unitPane"); map.getPane("unitPane").style.zIndex = 300;
  map.createPane("dryPane"); map.getPane("dryPane").style.zIndex = 310;
  map.createPane("firePane"); map.getPane("firePane").style.zIndex = 320;
  map.createPane("selPane"); map.getPane("selPane").style.zIndex = 330;

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

  // keadaan kontrol: tombol pil (data-layer) dan kontrol segmen (tema, horizon)
  const S = { kerawanan: true, hillshade: true, hotspots: true, khg: true, admin: true, canals: false, stations: true, struct: false };
  const T = { theme: "fire", fireKey: "p1", dryKey: "p14" };
  const HZ = { fire: [["p1", "Besok"], ["p3", "3 hari"]], dry: [["p7", "7 hari"], ["p14", "14 hari"]] };

  // titik api teramati (hanya Monitoring); sel peluang titik api (Monitoring: daftar prioritas; Prediksi: lapisan) dan pengeringan per sel (Prediksi)
  let hotData = null, hotLayer = null;
  if (!isPred && manifest.hotspots) {
    hotData = await getJson(DATA_DIR + manifest.hotspots.file);
    hotData.date_max = manifest.hotspots.date_max;
    hotLayer = L.geoJSON(hotData, { pane: "markerPane", pointToLayer: (f, ll) => L.circleMarker(ll, Object.assign({ pane: "markerPane" }, hotspotStyle(f.properties, hotData.date_max))),
      onEachFeature: (f, layer) => layer.bindPopup(hotspotPopupHtml(f.properties)) });
  }
  const fireGeo = manifest.fire ? await getJson(DATA_DIR + manifest.fire.file) : null;
  const dryGeo = isPred && manifest.dryness ? await getJson(DATA_DIR + manifest.dryness.file) : null;
  if (isPred && !fireGeo) T.theme = "dry";
  const byId = { fire: new Map(), dry: new Map() };
  (fireGeo ? fireGeo.features : []).forEach(f => byId.fire.set(cellKey(f), f));
  (dryGeo ? dryGeo.features : []).forEach(f => byId.dry.set(cellKey(f), f));
  let sel = null, selLayer = null;
  let fireLayer = null, dryLayer = null;
  if (isPred && fireGeo) {
    fireLayer = L.geoJSON(fireGeo, { pane: "firePane", style: f => fireCellStyle(f.properties, manifest.fire, opacity, T.fireKey), onEachFeature: (f, layer) => layer.on("click", () => select(cellKey(f))) });
  }
  if (isPred && dryGeo) {
    dryLayer = L.geoJSON(dryGeo, { pane: "dryPane", style: f => dryCellStyle(f.properties, manifest.dryness, opacity, T.dryKey), onEachFeature: (f, layer) => layer.on("click", () => select(cellKey(f))) });
  }

  const toggle = (layer, wanted) => {
    if (!layer) return;
    if (wanted && !map.hasLayer(layer)) map.addLayer(layer);
    if (!wanted && map.hasLayer(layer)) map.removeLayer(layer);
  };
  const syncKerawanan = () => {
    const z = map.getZoom(), want = isPred ? S.struct : S.kerawanan;
    tileLayers.forEach(l => toggle(l, want));
    toggle(unitLayer, want && unitLevel && z <= unitLevel.maxZoom);
    if ($("level-note")) $("level-note").textContent = k ? `Tingkat tampilan peta kerentanan pada zoom ini: ${want ? levelLabel(k.levels, z) : "lapisan mati"}.` : "";
  };
  const syncHillshade = () => toggle(hs, S.hillshade);
  const syncLines = () => { toggle(lines.khg, S.khg); toggle(lines.admin, S.admin); toggle(lines.canals, S.canals); };
  const syncPoints = () => { toggle(hotLayer, S.hotspots); toggle(fireLayer, isPred && T.theme === "fire"); toggle(dryLayer, isPred && T.theme === "dry"); };

  // stasiun
  const gj = await getJson(DATA_DIR + manifest.stations.file);
  const stationLayers = new Map();
  const styleFor = f => {
    const p = f.properties, stale = isStale(p.last_date, manifest.data_through);
    return stale ? { fillColor: NODATA_COLOR, fillOpacity: 0.15, color: "#555", weight: 1.5, dashArray: "3 3", className: "station-marker" }
                 : { fillColor: wlColor(p.wl_last_cm), fillOpacity: 1, color: "#ffffff", weight: 2, className: "station-marker" };   // lingkaran putih + bayangan: terbaca di atas warna apa pun
  };
  const markers = L.geoJSON(gj, {
    pointToLayer: (f, ll) => L.circleMarker(ll, Object.assign({ pane: "markerPane", radius: 7 }, styleFor(f))),
    onEachFeature: (f, layer) => {
      stationLayers.set(String(f.properties.id), layer);
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
        layer.setPopupContent(stationPopupHtml(p, manifest.validation, spark, isPred));
      });
    }
  });
  const syncStations = () => toggle(markers, S.stations);

  // lapisan teknis (hanya dengan --advanced-layers)
  const overlays = manifest.layers.map(l => L.imageOverlay(DATA_DIR + l.file, l.bounds, { opacity: 0.7 }));
  const supportEl = $("support");
  supportEl.innerHTML = manifest.layers.length
    ? manifest.layers.map((l, i) => `<label><input type="checkbox" data-i="${i}"> ${l.title}</label>`).join("<br>") : "";
  let supportLegend = "";
  const ss = $("support-sect"); if (!manifest.layers.length && ss) ss.style.display = "none";
  supportEl.addEventListener("change", e => {
    const i = Number(e.target.dataset.i);
    toggle(overlays[i], e.target.checked);
    supportLegend = e.target.checked ? legendHtml(manifest.layers[i]) : "";
    renderLegends();
  });

  // pemilihan sel: kotak tebal di peta, panel rincian (Prediksi) dan penanda di daftar
  const activeMap = () => byId[T.theme];
  const markPressed = () => document.querySelectorAll("[data-cell]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.cell === sel)));
  const renderPanel = () => {
    const el = $("cell-panel");
    if (!el || sel === null) return;
    el.innerHTML = cellPanelHtml({ theme: T.theme, id: sel, f: activeMap().get(sel), other: byId[T.theme === "fire" ? "dry" : "fire"].get(sel), fire: manifest.fire, dry: manifest.dryness, nTop: fireGeo ? fireGeo.features.length : 0 });
  };
  function select(id, fly) {
    sel = id;
    const f = activeMap().get(id) || byId.fire.get(id) || byId.dry.get(id);
    if (selLayer) { map.removeLayer(selLayer); selLayer = null; }
    if (f) {
      selLayer = L.polygon(f.geometry.coordinates[0].map(([lo, la]) => [la, lo]), { pane: "selPane", color: "#2A1A14", weight: 3, fill: false, interactive: false }).addTo(map);
      if (fly) map.fitBounds(selLayer.getBounds(), { maxZoom: 13, padding: [40, 40] });
    }
    renderPanel(); markPressed();
  }

  // ---- Prediksi: tema, horizon, judul, legenda, daftar teratas, kartu kepercayaan
  let scores = null;
  const hzKey = () => (T.theme === "fire" ? T.fireKey : T.dryKey);
  const topRows = () => {
    const feats = T.theme === "fire" ? (fireGeo ? fireGeo.features : []) : (dryGeo ? dryGeo.features : []);
    return T.theme === "fire" ? [...feats].sort((a, b) => a.properties.rank - b.properties.rank).slice(0, 5) : [...feats].sort((a, b) => b.properties[hzKey()] - a.properties[hzKey()]).slice(0, 5);
  };
  const MAP_TITLE = { p1: "Peluang ada titik api besok", p3: "Peluang ada titik api dalam 3 hari", p7: "Peluang muka air turun ≥ 10 cm dalam 7 hari", p14: "Peluang muka air turun ≥ 10 cm dalam 14 hari" };
  const renderTheme = () => {
    if (!isPred) return;
    document.querySelectorAll("#seg-theme button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.theme === T.theme)));
    $("seg-hz").innerHTML = HZ[T.theme].map(([key, label]) => `<button type="button" data-hz="${key}" aria-pressed="${key === hzKey()}">${label}</button>`).join("");
    $("map-title").textContent = MAP_TITLE[hzKey()];
    const src = T.theme === "fire" ? manifest.fire : manifest.dryness;
    $("page-sub").innerHTML = `Peluang, bukan kepastian. Klik sel untuk melihat rinciannya.${src ? ` · Terbit <b>${tglId(src.issue_date)}</b>` : ""}`;
    syncPoints();
    if (fireLayer) fireLayer.setStyle(f => fireCellStyle(f.properties, manifest.fire, opacity, T.fireKey));
    if (dryLayer) dryLayer.setStyle(f => dryCellStyle(f.properties, manifest.dryness, opacity, T.dryKey));
    const classes = T.theme === "fire" ? FIRE_CLASSES : DRY_CLASSES;
    $("legend-row").innerHTML = `<span style="font-weight:600">${MAP_TITLE[hzKey()]}</span><div style="display:flex;gap:6px">` +
      [...classes].reverse().map(c => `<div class="sw"><i style="background:${c.color}"></i><span>${c.short}</span></div>`).join("") + "</div><span>Garis tebal = sel terpilih</span>" +
      (T.theme === "fire" ? `<span class="note">Hanya ${manifest.fire && manifest.fire.top_fraction ? fmt(manifest.fire.top_fraction * 100, 0) + "% " : ""}sel teratas menurut peluang besok yang digambar, juga untuk horizon 3 hari.</span>`
                          : (manifest.dryness && manifest.dryness.cap_class >= 1 ? "" : `<span class="note">Warna dipucatkan: model belum terbukti mengalahkan pembanding.</span>`));
    $("top-title").textContent = T.theme === "fire" ? "Sel teratas peluang titik api" : "Sel teratas peluang pengeringan";
    $("top-list").innerHTML = priorityHtml(topRows(), hzKey(), p => T.theme === "fire" ? `3 hari: ${pctTxt(p.p3)} · rata-rata bulan ini ${pctTxt(p.p1_klim)}` : `7 hari: ${pctTxt(p.p7)} · median 14 hari ${fmt(p.d14, 0)} cm`);
    $("trust").innerHTML = trustHtml({ theme: T.theme, fire: manifest.fire, dry: manifest.dryness, scores });
    const rows = topRows();
    if (sel === null || !activeMap().has(sel)) { if (rows.length) select(cellKey(rows[0])); else { sel = null; } } else select(sel);
    markPressed();
  };

  // ---- legenda dan teks "Tentang peta ini"
  const renderLegends = () => {
    if (!isPred) {
      $("maplegend").innerHTML = compactLegendHtml(S.kerawanan ? k : null, hotData && S.hotspots ? hotData : null);
      const bd = monitoringBadge(manifest);
      $("about-map").innerHTML = `<div class="badge ${bd.cls}">${esc(bd.text)}</div>` + [kerawananLegendHtml(k), hotData ? hotspotLegendHtml(manifest.hotspots) : "", stationLegendHtml(), driversHtml(manifest.drivers, "Faktor penyusun kondisi kini")].join("");
    } else {
      $("about-map").innerHTML = [T.theme === "dry" ? dryLegendHtml(manifest.dryness) : fireLegendHtml(manifest.fire), S.struct ? kerawananLegendHtml(k) : "", stationLegendHtml(),
        predictionSummaryHtml(manifest.fire, manifest.dryness), driversHtml(manifest.drivers, "Masukan model")].join("");
    }
    $("legend").innerHTML = supportLegend;
  };

  // ---- kontrol
  const syncAll = () => { syncKerawanan(); syncHillshade(); syncLines(); syncStations(); syncPoints(); };
  document.querySelectorAll("[data-layer]").forEach(b => {
    const key = b.dataset.layer;
    b.setAttribute("aria-pressed", String(!!S[key]));
    b.addEventListener("click", () => { S[key] = !S[key]; b.setAttribute("aria-pressed", String(S[key])); syncAll(); renderLegends(); });
  });
  if (isPred) {
    document.querySelectorAll("#seg-theme button").forEach(b => { b.disabled = (b.dataset.theme === "fire" ? !fireGeo : !dryGeo); });
    $("seg-theme").addEventListener("click", e => { const b = e.target.closest("button[data-theme]"); if (b && !b.disabled && b.dataset.theme !== T.theme) { T.theme = b.dataset.theme; renderTheme(); renderLegends(); } });
    $("seg-hz").addEventListener("click", e => {
      const b = e.target.closest("button[data-hz]");
      if (!b) return;
      T[T.theme === "fire" ? "fireKey" : "dryKey"] = b.dataset.hz; renderTheme(); renderLegends();
    });
  }
  document.addEventListener("click", e => {
    const c = e.target.closest("[data-cell]");
    if (c) { select(c.dataset.cell, true); return; }
    const s = e.target.closest("[data-sid]");
    const l = s && stationLayers.get(s.dataset.sid);
    if (l) { map.setView(l.getLatLng(), Math.max(map.getZoom(), 12)); l.fire("click"); }
  });
  map.on("zoomend", syncKerawanan);
  $("opacity").addEventListener("input", e => {
    opacity = Number(e.target.value);
    tileLayers.forEach(l => l.setOpacity(opacity));
    if (unitLayer) unitLayer.setStyle({ fillOpacity: opacity });
    if (fireLayer) fireLayer.setStyle(f => fireCellStyle(f.properties, manifest.fire, opacity, T.fireKey));
    if (dryLayer) dryLayer.setStyle(f => dryCellStyle(f.properties, manifest.dryness, opacity, T.dryKey));
    overlays.forEach(o => o.setOpacity(Math.min(opacity, 0.8)));
  });

  // ---- isi kartu halaman
  if (isPred) {
    $("evidence").innerHTML = evidenceHtml([{ label: "Titik api", badge: fireBadge(manifest.fire) }, { label: "Pengeringan per sel", badge: dryBadge(manifest.dryness) }, { label: "Prakiraan stasiun", badge: validationBadge(manifest.validation) }]);
    Api.get("scores").then(r => { scores = r; $("trust").innerHTML = trustHtml({ theme: T.theme, fire: manifest.fire, dry: manifest.dryness, scores }); }, () => { /* tanpa 20: kartu menampilkan "belum ada" */ });
    if (!fireGeo && !dryGeo) $("page-sub").textContent = "Belum ada prediksi (jalankan 13, 14, dan 15, lalu 09).";
    renderTheme();
  } else {
    $("asof").textContent = `Data sampai ${tglId(manifest.data_through)}`;
    $("status-text").textContent = statusText(gj.features, hotData);
    $("kpis").innerHTML = kpiHtml(gj.features, hotData, manifest, null);
    Api.get("collections/tasks/items").then(r => { $("kpis").innerHTML = kpiHtml(gj.features, hotData, manifest, r.features); }, () => { /* tanpa 20: kartu tugas dilewati */ });
    $("prio-list").innerHTML = priorityHtml(topRows(), "p1", p => `3 hari: ${pctTxt(p.p3)} · rata-rata bulan ini ${pctTxt(p.p1_klim)}`);
    $("prio-status").innerHTML = manifest.fire ? evidenceHtml([{ label: "Kepercayaan model titik api", badge: fireBadge(manifest.fire) }]) : "";
    $("stn-list").innerHTML = stationRowsHtml(gj.features);
    document.querySelectorAll("#stn-list [data-sid]").forEach(async b => {
      try {
        const s = await getJson(DATA_DIR + manifest.stations.series_dir + b.dataset.sid + ".json");
        b.querySelector(".spark").innerHTML = sparklineSvg(s.wl_cm.slice(-30));
      } catch (e) { /* tanpa deret waktu: baris tetap menampilkan nilai terakhir */ }
    });
    Api.get("collections/events/items", { days: 30 }).then(r => { $("rep-list").innerHTML = (r.tiruan ? "<span class=\"chip\">DATA TIRUAN</span>" : "") + reportsHtml(r.features); },
      () => { $("rep-list").innerHTML = "<div class=\"note\">Belum ada data laporan (jalankan 17 dan 20).</div>"; });
  }
  renderLegends();
  syncAll();
  if (k && k.bounds) map.fitBounds(k.bounds);
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { tglId, stationTrend, sparklineSvg, priorityHtml, reportsHtml, evidenceHtml, cellPanelHtml, trustHtml, compactLegendHtml, statusText, fmt, wlColor, wlClass, isStale, stationLegendHtml, trendText, predictionSentences, stationPopupHtml, sparklinePath, validationBadge, predictionTable, legendHtml, startupHint,
                     levelForZoom, levelLabel, classColor, unitStyle, boundaryStyle, unitPopupHtml, kerawananLegendHtml,
                     ageDays, hotspotColor, hotspotStyle, hotspotPopupHtml, hotspotLegendHtml, fireClass, fireCellStyle, firePopupHtml, fireLegendHtml, fireBadge, dryClass, dryCellStyle, dryPopupHtml, dryLegendHtml, dryBadge,
                     stationSummary, openTasks, kpiHtml, monitoringSummaryHtml, predictionSummaryHtml, driversHtml, monitoringBadge };
} else {
  main().catch(err => {
    const hint = startupHint(location.protocol, err.message);
    const text = document.getElementById("status-text") || document.getElementById("page-sub"), title = document.getElementById("status-title") || document.getElementById("page-title");
    if (title) title.textContent = "Data belum dapat dimuat";
    if (text) text.textContent = hint;
  });
}
