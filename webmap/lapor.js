"use strict";
// lapor.js: halaman Lapor. Formulir tetap di KoboToolbox; halaman ini hanya mengantar dan menyalin kode tugas (?tugas=T20261112-007).
// Berkas lokal, bukan dari zip web.
(function () {
  const $ = id => document.getElementById(id);
  const copy = async (text, btn, ok) => {
    try { await navigator.clipboard.writeText(text); }
    catch (e) { const t = document.createElement("textarea"); t.value = text; document.body.appendChild(t); t.select(); try { document.execCommand("copy"); } catch (e2) { /* abaikan */ } t.remove(); }
    const old = btn.textContent; btn.textContent = ok; setTimeout(() => { btn.textContent = old; }, 1600);
  };
  const form = $("open-form");
  if ($("copy-link") && form) $("copy-link").addEventListener("click", e => copy(form.href, e.currentTarget, "Tautan disalin"));
  const kode = (new URLSearchParams(location.search).get("tugas") || "").trim();
  if (/^T\d{8}-\d{3}$/.test(kode) && $("task-box")) {
    $("task-code").textContent = kode; $("task-box").hidden = false;
    $("copy-task").addEventListener("click", e => copy(kode, e.currentTarget, "Kode disalin"));
  }
})();
