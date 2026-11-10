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


// ---- titik api teramati (monitoring) ------------------------------------------
function ageDays(dateStr, refStr) {
  return Math.round((Date.parse(refStr) - Date.parse(dateStr)) / 86400000);
}

const HOT_AGE = [
  { max: 0, color: "#b10026", label: "hari ini" },
  { max: 3, color: "#fd8d3c", label: "1–3 hari lalu" },
  { max: 7, color: "#fed976", label: "4–7 hari lalu" },
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
  { min: 0.30, color: "#980043", label: "peluang ≥ 30%" },
  { min: 0.10, color: "#dd1c77", label: "10–30%" },
  { min: 0.03, color: "#df65b0", label: "3–10%" },
  { min: 0, color: "#d7b5d8", label: "di bawah 3% (tetap 5% teratas)" },
];

function fireClass(p) {
  return FIRE_CLASSES.find(c => p >= c.min) || FIRE_CLASSES[FIRE_CLASSES.length - 1];
}

function fireCellStyle(props, fire, opacity = 0.85) {
  const c = fireClass(props[fire.primary_key || "p1"]).color;
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
  { min: 0.60, color: "#bd0026", label: "≥ 60%" },
  { min: 0.45, color: "#f03b20", label: "45–60%" },
  { min: 0.30, color: "#fd8d3c", label: "30–45%" },
  { min: 0.15, color: "#fecc5c", label: "15–30%" },
  { min: 0, color: "#ffffb2", label: "di bawah 15%" },
];

function dryClass(p) {
  return DRY_CLASSES.find(c => p >= c.min) || DRY_CLASSES[DRY_CLASSES.length - 1];
}

function dryCellStyle(props, dry, opacity = 0.85) {
  const o = dry && dry.cap_class >= 1 ? opacity : opacity * 0.55;     // kepercayaan rendah: lebih transparan
  const c = dryClass(props.p14).color;
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

async function main() {
  // Dari file:// peramban tidak mengirim Referer, dan server tile OSM menolak (403 "Access blocked"). Jangan minta tile sama sekali; tampilkan petunjuk.
  if (location.protocol === "file:") throw new Error("file-protocol");
  const $ = id => document.getElementById(id);
  const on = id => { const e = $(id); return !!(e && e.checked); };
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
  $("meta").innerHTML =
    `Versi ${manifest.version} &middot; dibuat ${manifest.generated_at}<br>Data sampai ${manifest.data_through || "–"} &middot; tanggal terbit prediksi ${manifest.issue_date || "–"}`;
  const badges = PAGE === "prediction" ? [fireBadge(manifest.fire), dryBadge(manifest.dryness), validationBadge(manifest.validation)] : [monitoringBadge(manifest)];
  const badgeEl = $("badge");
  badgeEl.className = "badge " + badges[0].cls;
  badgeEl.textContent = badges[0].text;
  const badge2 = $("badge2");
  if (badge2 && badges[1]) { badge2.className = "badge " + badges[1].cls; badge2.textContent = badges[1].text; }
  const badge3 = $("badge3");
  if (badge3 && badges[2]) { badge3.className = "badge " + badges[2].cls; badge3.textContent = "Prakiraan muka air stasiun: " + badges[2].text; }
  $("attrib").innerHTML = "<p>" + manifest.attribution.join("</p><p>") + "</p><p><b>" + manifest.disclaimer + "</b></p>";
  map.setView(manifest.center, 11);
  map.createPane("hillshadePane"); map.getPane("hillshadePane").style.zIndex = 240;
  map.createPane("kerawananPane"); map.getPane("kerawananPane").style.zIndex = 250;
  map.createPane("unitPane"); map.getPane("unitPane").style.zIndex = 300;
  map.createPane("dryPane"); map.getPane("dryPane").style.zIndex = 310;
  map.createPane("firePane"); map.getPane("firePane").style.zIndex = 320;

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

  // titik api teramati (hanya halaman monitoring) dan peluang titik api (hanya halaman prediksi)
  let hotData = null, hotLayer = null, fireLayer = null, dryLayer = null;
  if (PAGE === "monitoring" && manifest.hotspots) {
    hotData = await getJson(DATA_DIR + manifest.hotspots.file);
    hotData.date_max = manifest.hotspots.date_max;
    hotLayer = L.geoJSON(hotData, { pane: "markerPane", pointToLayer: (f, ll) => L.circleMarker(ll, Object.assign({ pane: "markerPane" }, hotspotStyle(f.properties, hotData.date_max))),
      onEachFeature: (f, layer) => layer.bindPopup(hotspotPopupHtml(f.properties)) });
  }
  if (PAGE === "prediction" && manifest.fire) {
    const fg = await getJson(DATA_DIR + manifest.fire.file);
    fireLayer = L.geoJSON(fg, { pane: "firePane", style: f => fireCellStyle(f.properties, manifest.fire, opacity),
      onEachFeature: (f, layer) => layer.bindPopup(firePopupHtml(f.properties, manifest.fire)) });
  }
  if (PAGE === "prediction" && manifest.dryness) {
    const dg = await getJson(DATA_DIR + manifest.dryness.file);
    dryLayer = L.geoJSON(dg, { pane: "dryPane", style: f => dryCellStyle(f.properties, manifest.dryness, opacity),
      onEachFeature: (f, layer) => layer.bindPopup(dryPopupHtml(f.properties, manifest.dryness)) });
  }

  const toggle = (layer, wanted) => {
    if (!layer) return;
    if (wanted && !map.hasLayer(layer)) map.addLayer(layer);
    if (!wanted && map.hasLayer(layer)) map.removeLayer(layer);
  };
  const syncKerawanan = () => {
    const z = map.getZoom(), want = on("chk-kerawanan") || on("theme-struct");
    tileLayers.forEach(l => toggle(l, want));
    toggle(unitLayer, want && unitLevel && z <= unitLevel.maxZoom);
    if ($("level")) $("level").textContent = want && k ? levelLabel(k.levels, z) : "–";
  };
  const syncHillshade = () => toggle(hs, on("chk-hillshade"));
  const syncLines = () => { toggle(lines.khg, on("chk-khg")); toggle(lines.admin, on("chk-admin")); toggle(lines.canals, on("chk-canals")); };
  const syncPoints = () => { toggle(hotLayer, on("chk-hotspots")); toggle(fireLayer, on("chk-fire") || on("theme-fire")); toggle(dryLayer, on("theme-dry")); };

  // stasiun
  const gj = await getJson(DATA_DIR + manifest.stations.file);
  const styleFor = f => {
    const p = f.properties, stale = isStale(p.last_date, manifest.data_through);
    return stale ? { fillColor: NODATA_COLOR, fillOpacity: 0.15, color: "#555", weight: 1.5, dashArray: "3 3", className: "station-marker" }
                 : { fillColor: wlColor(p.wl_last_cm), fillOpacity: 1, color: "#ffffff", weight: 2, className: "station-marker" };   // lingkaran putih + bayangan: terbaca di atas warna apa pun
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
        layer.setPopupContent(stationPopupHtml(p, manifest.validation, spark, PAGE === "prediction"));
      });
    }
  });
  const syncStations = () => toggle(markers, on("chk-stations"));

  // lapisan teknis (hanya dengan --advanced-layers)
  const overlays = manifest.layers.map(l => L.imageOverlay(DATA_DIR + l.file, l.bounds, { opacity: 0.7 }));
  const supportEl = $("support");
  supportEl.innerHTML = manifest.layers.length
    ? manifest.layers.map((l, i) => `<label><input type="checkbox" data-i="${i}"> ${l.title}</label>`).join("<br>") : "";
  let supportLegend = "";
  const renderLegend = () => {
    const theme = on("theme-dry") ? dryLegendHtml(manifest.dryness) : (on("theme-struct") ? kerawananLegendHtml(k) : fireLegendHtml(manifest.fire));
    const parts = PAGE === "prediction" ? [theme, stationLegendHtml()]
                                         : [kerawananLegendHtml(k), hotData ? hotspotLegendHtml(manifest.hotspots) : "", stationLegendHtml()];
    $("legendbox").innerHTML = parts.join("");
    $("legend").innerHTML = supportLegend;
  };
  const ss = $("support-sect"); if (!manifest.layers.length && ss && ss.style) ss.style.display = "none";
  supportEl.addEventListener("change", e => {
    const i = Number(e.target.dataset.i);
    toggle(overlays[i], e.target.checked);
    supportLegend = e.target.checked ? legendHtml(manifest.layers[i]) : "";
    renderLegend();
  });

  // ringkasan dan faktor penyusun
  if ($("summary")) $("summary").innerHTML = PAGE === "prediction" ? predictionSummaryHtml(manifest.fire, manifest.dryness) : monitoringSummaryHtml(gj.features, hotData, manifest);
  if ($("drivers")) $("drivers").innerHTML = driversHtml(manifest.drivers, PAGE === "prediction" ? "Masukan model" : "Faktor penyusun kondisi kini");

  const hook = (id, fn) => { const e = $(id); if (e) e.addEventListener("change", fn); };
  hook("chk-kerawanan", syncKerawanan); hook("chk-hillshade", syncHillshade);
  ["chk-khg", "chk-admin", "chk-canals"].forEach(id => hook(id, syncLines));
  hook("chk-stations", syncStations); hook("chk-hotspots", syncPoints); hook("chk-fire", syncPoints);
  ["theme-fire", "theme-dry", "theme-struct"].forEach(id => hook(id, () => { syncKerawanan(); syncPoints(); renderLegend(); }));
  map.on("zoomend", syncKerawanan);
  $("opacity").addEventListener("input", e => {
    opacity = Number(e.target.value);
    tileLayers.forEach(l => l.setOpacity(opacity));
    if (unitLayer) unitLayer.setStyle({ fillOpacity: opacity });
    if (fireLayer) fireLayer.setStyle(f => fireCellStyle(f.properties, manifest.fire, opacity));
    if (dryLayer) dryLayer.setStyle(f => dryCellStyle(f.properties, manifest.dryness, opacity));
    overlays.forEach(o => o.setOpacity(Math.min(opacity, 0.8)));
  });

  syncKerawanan(); syncHillshade(); syncLines(); syncStations(); syncPoints(); renderLegend();
  if (k && k.bounds) map.fitBounds(k.bounds);
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { fmt, wlColor, wlClass, isStale, stationLegendHtml, trendText, predictionSentences, stationPopupHtml, sparklinePath, validationBadge, predictionTable, legendHtml, startupHint,
                     levelForZoom, levelLabel, classColor, unitStyle, boundaryStyle, unitPopupHtml, kerawananLegendHtml,
                     ageDays, hotspotColor, hotspotStyle, hotspotPopupHtml, hotspotLegendHtml, fireClass, fireCellStyle, firePopupHtml, fireLegendHtml, fireBadge, dryClass, dryCellStyle, dryPopupHtml, dryLegendHtml, dryBadge,
                     stationSummary, monitoringSummaryHtml, predictionSummaryHtml, driversHtml, monitoringBadge };
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
