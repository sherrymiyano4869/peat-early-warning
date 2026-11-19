/* Halaman petugas: daftar tugas dari API v1 dan pencatatan status kunjungan (PATCH).
   Server API berjalan -> disimpan tambah-saja di server. Tanpa server (cermin statis) -> mode demo, hanya di peramban ini. */
const STATUS = {
  belum: ["Belum mulai", "#F3ECDF", "#2A1A14"],
  dalam_perjalanan: ["Dalam perjalanan", "#FBEBC4", "#5C4208"],
  diperiksa: ["Sudah diperiksa", "#F6E0CF", "#6E2717"],
  tidak_terjangkau: ["Tidak terjangkau", "#F6DDD6", "#862E1C"],
};
const NEEDS_VISIT = ["diperiksa", "tidak_terjangkau"];
const DEMO_KEY = "peat_demo_tasks";
const KOBO_HASIL = { kejadian: "Hasil Kobo: ada kejadian", nihil: "Hasil Kobo: nihil" };

const esc = t => String(t ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const isDone = p => p.hasil !== "belum" || NEEDS_VISIT.includes(p.status_lapangan);
const center = f => { const r = f.geometry.coordinates[0].slice(0, 4); return [r.reduce((a, c) => a + c[1], 0) / 4, r.reduce((a, c) => a + c[0], 0) / 4]; };
const wibNow = () => new Date(Date.now() + 7 * 3600e3).toISOString().slice(0, 16);   // nilai datetime-local dalam WIB

const state = { tasks: [], issue: null, server: false, filter: "all", active: null, pick: "belum", token: sessionStorage.getItem("peat_token") || "" };
const $ = id => document.getElementById(id);

function demoLoad() { try { return JSON.parse(localStorage.getItem(DEMO_KEY)) || {}; } catch (e) { return {}; } }
function demoSave(id, patch) { try { const d = demoLoad(); d[id] = { ...d[id], ...patch }; localStorage.setItem(DEMO_KEY, JSON.stringify(d)); } catch (e) { /* penyimpanan dimatikan: perubahan hanya di layar */ } }

function render() {
  const open = state.tasks.filter(f => !isDone(f.properties)).length;
  $("pt-count").textContent = `${open} terbuka`;
  $("pt-date").textContent = state.issue ? `Terbit ${state.issue}` : "";
  const list = state.tasks.filter(f => state.filter === "all" || (state.filter === "open") === !isDone(f.properties));
  $("pt-list").innerHTML = list.length ? list.map(f => {
    const p = f.properties, s = STATUS[p.status_lapangan] || STATUS.belum, [lat, lon] = center(f);
    const extra = [KOBO_HASIL[p.hasil], p.dikunjungi_pada ? `kunjungan ${p.dikunjungi_pada.replace("T", " ").replace("Z", " UTC")}` : ""].filter(Boolean).join(" · ");
    return `<article class="pt-card"><div class="pt-row"><div><h2>Sel ${esc(p.cell_id)}</h2><div class="small">Tugas ${esc(p.id_tugas)}${extra ? " · " + esc(extra) : ""}</div></div>
      <span class="pt-pill" style="background:${s[1]};color:${s[2]}">${s[0]}</span></div>
      <div class="pt-btns"><a class="pt-btn" target="_blank" rel="noopener" href="https://www.openstreetmap.org/?mlat=${lat.toFixed(5)}&mlon=${lon.toFixed(5)}#map=16/${lat.toFixed(5)}/${lon.toFixed(5)}">Navigasi</a>
      <button type="button" class="pt-btn primary" data-id="${esc(p.id_tugas)}">Perbarui status</button></div></article>`;
  }).join("") : '<div class="small">Tidak ada tugas pada saringan ini.</div>';
}

function renderOpts() {
  $("pt-opts").innerHTML = Object.keys(STATUS).map(k => `<button type="button" class="pt-opt" role="radio" aria-checked="${state.pick === k}" data-k="${k}"><i></i>${STATUS[k][0]}</button>`).join("");
  $("pt-visit-box").hidden = !NEEDS_VISIT.includes(state.pick);
}

function openSheet(id) {
  const f = state.tasks.find(x => x.properties.id_tugas === id), p = f.properties;
  state.active = f; state.pick = p.status_lapangan || "belum";
  $("pt-sheet-title").textContent = `Status sel ${p.cell_id}`;
  $("pt-note-in").value = ""; $("pt-err").textContent = "";
  $("pt-visit").value = p.dikunjungi_pada ? new Date(Date.parse(p.dikunjungi_pada) + 7 * 3600e3).toISOString().slice(0, 16) : wibNow();
  $("pt-token-box").hidden = !state.server || !!state.token;
  renderOpts(); $("pt-sheet").hidden = false; $("pt-opts").querySelector('[aria-checked="true"]').focus();
}
const closeSheet = () => { $("pt-sheet").hidden = true; };

async function save() {
  const p = state.active.properties, body = { status: state.pick };
  const note = $("pt-note-in").value.trim();
  if (note) body.catatan = note;
  if (NEEDS_VISIT.includes(state.pick)) {
    if (!$("pt-visit").value) { $("pt-err").textContent = "Isi waktu kunjungan."; return; }
    body.dikunjungi_pada = `${$("pt-visit").value}:00+07:00`;
  }
  try {
    if (state.server) {
      const token = state.token || $("pt-token").value.trim();
      if (!token) { $("pt-err").textContent = "Isi kunci tim."; return; }
      const updated = await Api.patch(`collections/tasks/items/${encodeURIComponent(p.id_tugas)}`, body, token);
      state.token = token; sessionStorage.setItem("peat_token", token);
      state.tasks[state.tasks.indexOf(state.active)] = updated;
    } else {
      const patch = { status_lapangan: body.status, dikunjungi_pada: body.dikunjungi_pada ? new Date(body.dikunjungi_pada).toISOString().slice(0, 19) + "Z" : p.dikunjungi_pada };
      demoSave(p.id_tugas, patch); Object.assign(p, patch);
    }
    closeSheet(); render();
  } catch (e) {
    if (/Bearer|berwenang/i.test(e.message)) { state.token = ""; sessionStorage.removeItem("peat_token"); }
    $("pt-err").textContent = e.message;
  }
}

async function main() {
  state.server = await Api.isServer();
  const b = $("pt-banner"); b.hidden = false;
  b.className = "pt-banner" + (state.server ? " ok" : "");
  b.textContent = state.server ? "Terhubung ke server API: status disimpan tambah-saja." : "Mode demo: server API tidak berjalan, status hanya tersimpan di peramban ini.";
  const r = await Api.get("collections/tasks/items");
  state.issue = r.issue_date; state.tasks = r.features;
  if (!state.server) { const d = demoLoad(); state.tasks.forEach(f => Object.assign(f.properties, d[f.properties.id_tugas] || {})); }
  render();
}

document.querySelectorAll(".pt-filters button").forEach(btn => btn.addEventListener("click", () => {
  state.filter = btn.dataset.f;
  document.querySelectorAll(".pt-filters button").forEach(x => x.setAttribute("aria-pressed", String(x === btn)));
  render();
}));
$("pt-list").addEventListener("click", e => { const b = e.target.closest("button[data-id]"); if (b) openSheet(b.dataset.id); });
$("pt-opts").addEventListener("click", e => { const b = e.target.closest("button[data-k]"); if (b) { state.pick = b.dataset.k; renderOpts(); } });
$("pt-cancel").addEventListener("click", closeSheet);
$("pt-save").addEventListener("click", save);
document.addEventListener("keydown", e => { if (e.key === "Escape" && !$("pt-sheet").hidden) closeSheet(); });
main().catch(err => { $("pt-list").textContent = "Tugas belum dapat dimuat: " + err.message + " (jalankan 20 dan 21, lalu buka lewat server)."; });
