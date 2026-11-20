"use strict";
// i18n.js: pilihan bahasa ID/EN. Teks Indonesia tetap menjadi sumber di HTML; bahasa Inggris dipasang dengan mencocokkan teks (kamus webmap/i18n-en.js).
//   - Pilihan disimpan di localStorage ("lang") dan bisa dipaksa lewat ?lang=en atau ?lang=id.
//   - Simpul teks dan atribut aria-label, title, alt, placeholder yang punya padanan di kamus diganti; yang tidak ada dibiarkan (nama, istilah umum).
//   - Konten yang dibuat kemudian oleh JavaScript ikut diterjemahkan (MutationObserver) selama teksnya persis sama dengan kunci kamus.
//   - API untuk kode lain: window.I18N.t("teks Indonesia"), window.I18N.f("Stasiun di bawah {n} cm", {n: 40}), window.I18N.add({...}), window.I18N.set("en"), peristiwa "langchange".
// Berkas lokal, bukan dari zip web. Lihat docs/I18N.md.
(function () {
  const DICT = window.I18N_EN || {};
  const PARTIAL = [];   // halaman yang isinya belum diterjemahkan (menampilkan catatan di bahasa Inggris); kosong = semua sudah
  const ATTRS = ["aria-label", "title", "alt", "placeholder"];
  const norm = s => s.replace(/\s+/g, " ").trim();
  const has = Object.prototype.hasOwnProperty;
  // Pola untuk teks bervariabel (angka, tanggal, nama): [regex, pengganti]; {1} = tangkapan apa adanya, {1:n} = angka gaya Indonesia ke gaya Inggris,
  // {1:d} = nama bulan Indonesia ke Inggris, {1:t} = tangkapan diterjemahkan lewat kamus, {1:p} = bagian-bagian dipisah "; " diterjemahkan satu per satu.
  const RX = (window.I18N_EN_RX || []).map(([p, r]) => [new RegExp("^(?:" + p + ")$"), r]);
  const MON = { Mei: "May", Agu: "Aug", Okt: "Oct", Des: "Dec" };
  const numEn = v => v.replace(/(\d{1,3}(?:\.\d{3})+|\d+)(,\d+)?/g, (m, i, d) => i.replace(/\./g, ",") + (d ? "." + d.slice(1) : ""));
  const dateEn = v => v.replace(/\b(\d{1,2}) (Mei|Agu|Okt|Des)\b/g, (m, d, mo) => d + " " + MON[mo]);
  const conv = (v, f) => f === "n" ? numEn(v) : f === "d" ? dateEn(v) : f === "t" ? (tr(v) !== null ? tr(v) : v)
    : f === "p" ? v.split("; ").map(x => (tr(x) !== null ? tr(x) : x)).join("; ") : v;
  function tr(s) {
    const k = norm(s);
    if (!k) return null;
    if (has.call(DICT, k)) return DICT[k];
    for (const [re, r] of RX) {
      const m = k.match(re);
      if (m) return r.replace(/\{(\d+)(?::([ndtp]))?\}/g, (_, i, f) => conv(m[+i] === undefined ? "" : m[+i], f));
    }
    return null;
  }
  const store = (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* abaikan */ } };
  const load = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };

  const textOrig = new Map();   // simpul teks -> teks Indonesia asli
  const attrOrig = new Map();   // elemen -> {atribut: nilai Indonesia asli}
  let lang = "id", observer = null, titleOrig = null, noteEl = null;

  function doText(n) {
    const p = n.parentNode;
    if (!p || /^(SCRIPT|STYLE|NOSCRIPT)$/.test(p.nodeName)) return;
    const base = textOrig.has(n) ? textOrig.get(n) : n.nodeValue;
    const t = tr(base);
    if (t === null) return;
    if (!textOrig.has(n)) textOrig.set(n, base);
    const nv = base.match(/^\s*/)[0] + t + base.match(/\s*$/)[0];
    if (n.nodeValue !== nv) n.nodeValue = nv;
  }
  function doAttrs(el) {
    ATTRS.forEach(a => {
      const cur = el.getAttribute(a);
      if (cur === null) return;
      const o = attrOrig.get(el) || {};
      const base = has.call(o, a) ? o[a] : cur;
      const t = tr(base);
      if (t === null) return;
      o[a] = base; attrOrig.set(el, o);
      if (cur !== t) el.setAttribute(a, t);
    });
  }
  function walk(root) {
    if (root.nodeType === 3) { doText(root); return; }
    if (root.nodeType !== 1) return;
    doAttrs(root);
    const w = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    let n;
    while ((n = w.nextNode())) { if (n.nodeType === 3) doText(n); else doAttrs(n); }
  }
  function restore() {
    textOrig.forEach((base, n) => { if (n.isConnected && n.nodeValue !== base) n.nodeValue = base; });
    attrOrig.forEach((o, el) => { if (el.isConnected) Object.keys(o).forEach(a => el.setAttribute(a, o[a])); });
    textOrig.clear(); attrOrig.clear();
    if (titleOrig !== null) document.title = titleOrig;
  }

  function showNote(on) {
    if (noteEl) { noteEl.remove(); noteEl = null; }
    if (!on) return;
    const page = location.pathname.split("/").pop() || "index.html";
    let closed = false; try { closed = sessionStorage.getItem("i18n-note") === "1"; } catch (e) { /* abaikan */ }
    if (!PARTIAL.includes(page) || closed || !DICT.__partial) return;
    noteEl = document.createElement("div");
    noteEl.className = "i18n-note"; noteEl.setAttribute("role", "status");
    const span = document.createElement("span"); span.textContent = DICT.__partial;
    const b = document.createElement("button"); b.type = "button"; b.textContent = "×"; b.setAttribute("aria-label", DICT.__partial_close || "Close");
    b.addEventListener("click", () => { try { sessionStorage.setItem("i18n-note", "1"); } catch (e) { /* abaikan */ } showNote(false); });
    noteEl.append(span, b); document.body.appendChild(noteEl);
  }

  function apply(l, persist) {
    lang = l === "en" ? "en" : "id";
    document.documentElement.lang = lang;
    if (persist) store("lang", lang);
    document.querySelectorAll(".lang button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.lang === lang)));
    if (observer) { observer.disconnect(); observer = null; }
    if (lang === "en") {
      if (titleOrig === null) titleOrig = document.title;
      const tt = tr(titleOrig); if (tt !== null) document.title = tt;
      walk(document.body);
      observer = new MutationObserver(ms => ms.forEach(m => m.addedNodes.forEach(n => walk(n))));
      observer.observe(document.body, { childList: true, subtree: true });
    } else {
      restore();
    }
    showNote(lang === "en");
    document.dispatchEvent(new CustomEvent("langchange", { detail: { lang } }));
  }

  function buildToggle() {
    const bar = document.querySelector(".topbar");
    if (!bar || bar.querySelector(".lang")) return;
    const g = document.createElement("div");
    g.className = "lang"; g.setAttribute("role", "group"); g.setAttribute("aria-label", "Bahasa / Language");
    ["id", "en"].forEach(l => {
      const b = document.createElement("button");
      b.type = "button"; b.dataset.lang = l; b.textContent = l.toUpperCase(); b.setAttribute("aria-pressed", "false");
      b.addEventListener("click", () => apply(l, true));
      g.appendChild(b);
    });
    bar.appendChild(g);
  }

  window.I18N = {
    get lang() { return lang; },
    set: l => apply(l, true),
    t: s => (lang === "en" && tr(s) !== null ? tr(s) : s),
    f: (tpl, vars) => String(window.I18N.t(tpl)).replace(/\{(\w+)\}/g, (m, k) => (vars && has.call(vars, k) ? vars[k] : m)),   // kalimat bervariabel: kunci kamus memakai {nama}
    add: map => { Object.assign(DICT, map); if (lang === "en") walk(document.body); },
  };

  buildToggle();
  const q = new URLSearchParams(location.search).get("lang");
  apply(q === "en" || q === "id" ? q : (load("lang") === "en" ? "en" : "id"), q === "en" || q === "id");
})();
