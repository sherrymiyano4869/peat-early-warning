"use strict";
// Halaman Respons: buku besar kejadian (17), tugas pemeriksaan (19), sekat dan muka air lapangan (16), skor prospektif (18).
// Data: data/response.json dari scripts/20_export_response.py. Titik laporan kejadian tidak ada di data; hanya sel 1 km.
const BASEMAP = { url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png", attribution: "&copy; <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a> contributors", maxZoom: 19 };
const CATS = {   // warna Okabe-Ito dan Tol: tetap terbedakan pada buta warna merah-hijau
  keduanya: { color: "#D55E00", label: "Satelit dan laporan lapangan" },
  satelit: { color: "#E69F00", label: "Hanya satelit (belum ada laporan)" },
  laporan: { color: "#AA4499", label: "Hanya laporan, tingkat A/B (lolos dari satelit)" },
  laporan_c: { color: "#AA4499", label: "Laporan belum terverifikasi (tingkat C)", hollow: true },
  nihil: { color: "#56B4E9", label: "Diperiksa, tidak ada kejadian" },
};
const SEKAT = { baik: "#2c7bb6", rusak: "#dfc27d", jebol: "#a6611a" };
const WL = [[-40, "#2c7bb6", "≥ −40 cm"], [-80, "#dfc27d", "−40 s/d −80 cm"], [-120, "#a6611a", "−80 s/d −120 cm"], [-Infinity, "#543005", "< −120 cm"]];   // sama dengan stasiun SiTMAT
const TASK = { belum: "Belum diperiksa", nihil: "Diperiksa: tidak ada kejadian", kejadian: "Diperiksa: ada kejadian" };

const fmt = (x, d = 0) => (x === null || x === undefined || Number.isNaN(x)) ? "–" : Number(x).toLocaleString("id-ID", { minimumFractionDigits: d, maximumFractionDigits: d });
const pct = (k, n) => n ? fmt(100 * k / n, 0) + "%" : "–";
const tgl = s => new Date(s + "T00:00:00Z").toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const fieldAB = r => r.n_pos > 0 && (r.tingkat === "A" || r.tingkat === "B");
const bySat = r => r.n_viirs > 0 || r.n_match > 0;

// Kategori satu sel dari semua sel-harinya di jendela waktu. mode "satelit" = seolah laporan tidak ada.
function classifyCell(rows, mode) {
  const sat = rows.some(r => r.n_viirs > 0);
  if (mode === "satelit") return sat ? "satelit" : null;
  if (rows.some(r => r.n_pos > 0 && bySat(r)) || (sat && rows.some(fieldAB))) return "keduanya";
  if (sat) return "satelit";
  if (rows.some(fieldAB)) return "laporan";
  if (rows.some(r => r.n_pos > 0)) return "laporan_c";
  return rows.some(r => r.status === "nihil") ? "nihil" : null;
}

// Hitungan sel-hari di jendela: kolom "satelit" (tanpa laporan) dan "gabungan" (dengan laporan).
function counters(rows) {
  const n = f => rows.filter(f).length;
  const missed = r => fieldAB(r) && !bySat(r);
  return {
    kejadian: [n(r => r.n_viirs > 0), n(r => r.n_viirs > 0 || fieldAB(r))],
    terkonfirmasi: [0, n(r => r.n_pos > 0 && bySat(r))],
    lolos: [0, n(missed)],
    tetangga: [0, n(r => fieldAB(r) && r.n_viirs === 0 && r.n_match > 0)],
    lolos_membara: [0, n(r => missed(r) && r.membara)],
    nihil: [0, n(r => r.status === "nihil" && (r.tingkat === "A" || r.tingkat === "B"))],
    belum_verif: [0, n(r => r.n_pos > 0 && r.tingkat === "C")],
    kunjungan: [0, n(r => r.n_kunjungan > 0)],
    tindakan: [0, n(r => r.n_tindakan > 0)],
  };
}

function rowText(r) {
  const parts = [];
  if (r.n_viirs > 0) parts.push(`VIIRS ${r.n_viirs} deteksi`);
  if (r.n_pos > 0) parts.push(`${r.n_pos} laporan ${r.membara ? "membara" : (r.menyala ? "api" : "asap")} (tingkat ${r.tingkat}${r.n_match > 0 ? ", cocok dengan satelit" : ""})`);
  if (r.n_nihil > 0) parts.push(`${r.n_nihil} laporan nihil${r.status === "nihil" ? ` (tingkat ${r.tingkat})` : ""}`);
  if (r.n_tindakan > 0) parts.push("ada tindakan");
  if (r.konflik) parts.push("<b>konflik: nihil dan kejadian di sel-hari yang sama</b>");
  return `<li>${tgl(r.date)}: ${parts.join("; ") || "kunjungan lain (muka air atau sekat)"}</li>`;
}

function scoresHtml(s) {
  if (!s) return "<b>Apakah prediksi terbukti?</b><br><span class=\"small\">Belum ada skor. Jalankan 18_score_prospective.py lalu 20_export_response.py.</span>";
  const out = ["<b>Apakah prediksi terbukti?</b> <span class=\"small\">arsip prediksi lawan kejadian sesudahnya</span>"];
  const a = s.tugas_pemeriksaan && s.tugas_pemeriksaan.per_alasan;
  if (a && a.teratas && a.acak) {
    const p = s.tugas_pemeriksaan.fisher_teratas_lebih_besar_dari_acak_p;
    out.push(`<div><b>Tugas pemeriksaan.</b> Sel teratas: kejadian di ${a.teratas.kejadian} dari ${a.teratas.diperiksa} yang diperiksa (<b>${pct(a.teratas.kejadian, a.teratas.diperiksa)}</b>). ` +
             `Sel acak: ${a.acak.kejadian} dari ${a.acak.diperiksa} (<b>${pct(a.acak.kejadian, a.acak.diperiksa)}</b>).` + (p === undefined ? "" : ` Uji Fisher p = ${fmt(p, 3)}.`) + "</div>");
  }
  const h1 = s.titik_api && s.titik_api.h1;
  if (h1 && h1.viirs && h1.viirs.pr_auc_model !== undefined) {
    const line = (k, nama) => h1[k].pr_auc_model === undefined ? "" : `${nama}: PR-AUC ${fmt(h1[k].pr_auc_model, 3)} lawan klimatologi ${fmt(h1[k].pr_auc_klimatologi, 3)}, ${h1[k].n_positif} sel berkejadian. `;
    out.push(`<div><b>Peluang titik api besok</b> (${h1.viirs.n_terbitan} terbitan). ${line("viirs", "Kenyataan = satelit")}${line("buku", "Kenyataan = satelit + laporan")}` +
             `Lolos uji prospektif: <b>${h1.lolos_prospektif ? "ya" : "belum"}</b>.</div>`);
  }
  const w = s.muka_air_vs_indeks;
  if (w && w.spearman_rho !== undefined) {
    out.push(`<div><b>Indeks kerentanan lawan muka air lapangan.</b> Spearman ${fmt(w.spearman_rho, 2)} (selang 95% ${fmt(w.selang_95[0], 2)} s/d ${fmt(w.selang_95[1], 2)}) pada ${w.n_titik_dipakai} titik: ${w.kesimpulan}.</div>`);
  } else if (w && w.catatan) {
    out.push(`<div><b>Indeks kerentanan lawan muka air lapangan.</b> <span class="small">${w.catatan}</span></div>`);
  }
  return out.join("");
}

function legendHtml(mode, show) {
  const sw = c => `<span class="swatch" style="${c.hollow ? `background:transparent;border:2px dashed ${c.color}` : `background:${c.color}`}"></span>`;
  let h = "<h2>Kejadian per sel 1 km</h2>" + Object.entries(CATS).filter(([k]) => mode === "gabungan" || k === "satelit").map(([, c]) => `${sw(c)}${c.label}<br>`).join("");
  if (mode === "gabungan") h += "<span class=\"dot\" style=\"background:#fff;border:2px solid #111\"></span>Ada laporan membara<br>";
  if (show.top) h += "<h2>Prediksi</h2><span class=\"swatch\" style=\"background:transparent;border:1.5px solid #333\"></span>Sel berpeluang tertinggi<br>";
  if (show.tasks) h += "<h2>Tugas pemeriksaan</h2><span class=\"swatch\" style=\"background:transparent;border:2px dashed #0072B2\"></span>Belum diperiksa<br><span class=\"swatch\" style=\"background:transparent;border:2px solid #0072B2\"></span>Sudah diperiksa<br>";
  if (show.sekat) h += "<h2>Sekat kanal (kondisi terakhir)</h2>" + Object.entries(SEKAT).map(([k, c]) => `<span class="swatch" style="background:${c};transform:rotate(45deg)"></span>${k}<br>`).join("");
  if (show.water) h += "<h2>Muka air lapangan (bacaan terakhir)</h2>" + WL.map(([, c, l]) => `<span class="dot" style="background:${c}"></span>${l}<br>`).join("");
  return h + "<div class=\"small\">Sel 1 km, bukan titik laporan (privasi pelapor). Tanpa warna = tidak ada bukti, bukan berarti aman.</div>";
}

async function main() {
  if (location.protocol === "file:") throw new Error("Halaman dibuka lewat berkas (file://). Jalankan: python -m http.server -d webmap 8000, lalu buka http://localhost:8000/response.html");
  const $ = id => document.getElementById(id);
  const r = await fetch("data/response.json");
  if (!r.ok) throw new Error("data/response.json belum ada. Jalankan python scripts/20_export_response.py");
  const D = await r.json();
  const map = L.map("map").setView([-1.3, 104.0], 8);
  const base = (D.basemap && D.basemap.url) ? D.basemap : BASEMAP;
  L.tileLayer(base.url, { maxZoom: base.maxZoom || 19, attribution: base.attribution, className: "basemap-muted", referrerPolicy: "origin" }).addTo(map);
  L.control.scale({ metric: true, imperial: false }).addTo(map);
  const ring = id => D.cells[id].map(([lon, lat]) => [lat, lon]);
  const center = id => { const p = D.cells[id]; return [(p[0][1] + p[2][1]) / 2, (p[0][0] + p[2][0]) / 2]; };
  const all = Object.keys(D.cells);
  if (all.length) map.fitBounds(L.latLngBounds(all.flatMap(ring)).pad(0.1));

  $("meta").innerHTML = `Versi ${D.version} &middot; dibuat ${D.generated_at}<br>Buku besar ${tgl(D.date_min)} s/d ${tgl(D.date_max)}`;
  $("badge").className = "badge " + (D.tiruan ? "bad" : "warn");
  $("badge").innerHTML = D.tiruan ? "<b>DATA TIRUAN.</b> Laporan di halaman ini buatan untuk menguji alur. Angka di bawah bukan bukti kinerja."
                                  : "Prototipe riset, bukan peringatan resmi. Tingkat keyakinan laporan memakai aturan awal yang belum disetel.";
  $("scores").innerHTML = scoresHtml(D.scores);
  const pr = D.parameter;
  $("attrib").innerHTML = "Laporan lapangan dikumpulkan lewat KoboToolbox; identitas pelapor tidak disimpan dan titik laporan hanya ditampilkan per sel 1 km. " +
    "Titik api: VIIRS 375 m (NASA FIRMS). Satelit tidak dipakai sebagai bukti nihil karena awan, asap, dan api membara lolos dari deteksi." +
    (pr ? ` Laporan dianggap cocok dengan satelit bila berjarak ≤ ${fmt(pr.radius_m)} m dan ≤ ${fmt(pr.window_h)} jam (angka awal).` : "");

  const days = [];
  for (let t = Date.parse(D.date_min); t <= Date.parse(D.date_max); t += 86400000) days.push(new Date(t).toISOString().slice(0, 10));
  $("end").max = days.length - 1;
  $("end").value = days.length - 1;
  const groups = { events: L.layerGroup().addTo(map), top: L.layerGroup(), tasks: L.layerGroup(), sekat: L.layerGroup(), water: L.layerGroup() };

  (D.top_cells ? D.top_cells.features : []).forEach(f => L.polygon(f.geometry.coordinates[0].map(([lon, lat]) => [lat, lon]), { color: "#333", weight: 1.5, fill: false, interactive: false }).addTo(groups.top));
  D.tasks.items.forEach(t => L.polygon(ring(t.cell_id), { color: "#0072B2", weight: 2.5, dashArray: t.hasil === "belum" ? "5 5" : null, fill: false })
    .bindPopup(`<b>Tugas ${t.id_tugas}</b><br>Terbit ${D.tasks.issue_date}<br>${TASK[t.hasil]}`).addTo(groups.tasks));
  D.sekat.forEach(s => L.marker([s.lat, s.lon], { icon: L.divIcon({ className: "", iconSize: [12, 12], html: `<div style="width:10px;height:10px;transform:rotate(45deg);border:1px solid #222;background:${SEKAT[s.kondisi] || "#9e9e9e"}"></div>` }) })
    .bindPopup(`<b>Sekat ${s.titik}</b><br>Kondisi terakhir: <b>${s.kondisi || "–"}</b> (${tgl(s.tanggal)})<br>${s.n} laporan`).addTo(groups.sekat));
  D.water.forEach(w => L.circleMarker([w.lat, w.lon], { radius: 6, color: "#222", weight: 1, fillOpacity: 1, fillColor: WL.find(c => w.muka_air_cm >= c[0])[1] })
    .bindPopup(`<b>Titik muka air ${w.titik}</b><br>Bacaan terakhir (${tgl(w.tanggal)}): <b>${fmt(w.muka_air_cm)} cm</b><br>${w.n} bacaan`).addTo(groups.water));

  function update() {
    const mode = $("mode-sat").checked ? "satelit" : "gabungan";
    const iEnd = +$("end").value, span = +$("span").value || days.length;
    const d1 = days[iEnd], d0 = days[Math.max(0, iEnd - span + 1)];
    $("range").textContent = d0 === d1 ? tgl(d1) : `${tgl(d0)} – ${tgl(d1)}`;
    const rows = D.ledger.filter(x => x.date >= d0 && x.date <= d1);
    const byCell = new Map();
    rows.forEach(x => byCell.set(x.cell_id, (byCell.get(x.cell_id) || []).concat(x)));
    groups.events.clearLayers();
    byCell.forEach((rs, id) => {
      const cat = classifyCell(rs, mode);
      if (!cat) return;
      const c = CATS[cat];
      const shown = mode === "satelit" ? rs.filter(x => x.n_viirs > 0).map(x => `<li>${tgl(x.date)}: VIIRS ${x.n_viirs} deteksi</li>`) : rs.slice().sort((a, b) => a.date.localeCompare(b.date)).map(rowText);
      L.polygon(ring(id), { color: c.color, weight: c.hollow ? 2 : 1, dashArray: c.hollow ? "4 4" : null, fillColor: c.color, fillOpacity: c.hollow ? 0 : 0.75 })
        .bindPopup(`<b>${c.label}</b><ul style="margin:4px 0;padding-left:18px">${shown.join("")}</ul>`).addTo(groups.events);
      if (mode === "gabungan" && rs.some(x => x.membara)) L.circleMarker(center(id), { radius: 4, color: "#111", weight: 2, fillColor: "#fff", fillOpacity: 1, interactive: false }).addTo(groups.events);
    });

    const k = counters(rows), col = mode === "satelit" ? 0 : 1;
    const line = (label, v, cls = "") => `<tr class="${cls}"><td>${label}</td><td class="${col === 0 ? "on" : ""}">${v[0] === null ? "–" : fmt(v[0])}</td><td class="${col === 1 ? "on" : ""}">${fmt(v[1])}${v[1] > v[0] && v[0] !== null ? ` <span class="plus">+${fmt(v[1] - v[0])}</span>` : ""}</td></tr>`;
    const na = v => [null, v[1]];
    $("summary").innerHTML = "<b>Sebelum dan sesudah laporan</b> <span class=\"small\">sel-hari pada rentang ini</span>" +
      "<table class=\"pred cmp\"><tr><th></th><th>Hanya satelit</th><th>Dengan laporan</th></tr>" +
      line("Kejadian tercatat", k.kejadian) + line("&nbsp;&nbsp;dikonfirmasi di lapangan", na(k.terkonfirmasi)) + line("&nbsp;&nbsp;sel baru di sebelah deteksi satelit", na(k.tetangga)) + line("&nbsp;&nbsp;lolos dari satelit", na(k.lolos)) +
      line("&nbsp;&nbsp;&nbsp;&nbsp;di antaranya membara", na(k.lolos_membara)) + line("Diperiksa, tidak ada kejadian", na(k.nihil)) + line("Laporan belum terverifikasi", na(k.belum_verif)) +
      line("Sel-hari dikunjungi", na(k.kunjungan)) + line("Sel-hari dengan tindakan", na(k.tindakan)) + "</table>";
    const t = D.tasks.items, done = t.filter(x => x.hasil !== "belum");
    $("tasksum").innerHTML = t.length ? `<b>Tugas pemeriksaan</b> <span class="small">terbit ${D.tasks.issue_date}</span><br>${t.length} tugas, ${done.length} sudah diperiksa ` +
      `(${done.filter(x => x.hasil === "kejadian").length} ada kejadian, ${done.filter(x => x.hasil === "nihil").length} nihil)` : "<b>Tugas pemeriksaan</b><br><span class=\"small\">Belum ada daftar tugas (19).</span>";

    const show = { top: $("chk-top").checked && mode === "gabungan", tasks: $("chk-tasks").checked && mode === "gabungan", sekat: $("chk-sekat").checked && mode === "gabungan", water: $("chk-water").checked && mode === "gabungan" };
    Object.entries(show).forEach(([name, onNow]) => onNow ? groups[name].addTo(map) : map.removeLayer(groups[name]));
    document.querySelectorAll(".field-only").forEach(e => { e.style.opacity = mode === "gabungan" ? 1 : 0.4; });
    $("legendbox").innerHTML = legendHtml(mode, show);
  }
  ["mode-sat", "mode-all", "end", "span", "chk-top", "chk-tasks", "chk-sekat", "chk-water"].forEach(id => $(id).addEventListener("input", update));
  update();
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { classifyCell, counters, rowText, scoresHtml, legendHtml };
} else {
  main().catch(err => {
    document.getElementById("title").textContent = "Data belum dapat dimuat";
    const b = document.getElementById("badge");
    b.className = "badge bad";
    b.textContent = err.message;
  });
}
