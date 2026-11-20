/* Klien API v1: memakai server (v1/...) bila ada, kalau tidak cermin statis (data/v1/....json) dari scripts/21_export_api.py.
   Alamat relatif, jadi jalan di akar situs maupun di sub-folder (mis. GitHub Pages). Mode statis tidak punya penyaring dan PATCH. */
const Api = (() => {
  let serverMode = null;

  async function probe() {
    if (serverMode !== null) return serverMode;
    try {
      const r = await fetch("v1", { headers: { Accept: "application/json" } });
      serverMode = r.ok && (r.headers.get("content-type") || "").includes("json");
    } catch (e) { serverMode = false; }
    return serverMode;
  }

  async function get(path, params) {
    const q = params && Object.keys(params).length ? "?" + new URLSearchParams(params) : "";
    const url = (await probe()) ? `v1/${path}${q}` : `data/v1/${path}.json`;
    const r = await fetch(url);
    if (!r.ok) {
      const e = await r.json().catch(() => ({}));
      throw new Error(e.description || `${url} -> ${r.status}`);
    }
    return r.json();
  }

  async function patch(path, body, token) {
    if (!(await probe())) throw new Error("Server API tidak berjalan; perubahan tidak bisa disimpan.");
    const r = await fetch(`v1/${path}`, { method: "PATCH", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify(body) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.description || `PATCH -> ${r.status}`);
    return j;
  }

  return { get, patch, isServer: probe };
})();
if (typeof module !== "undefined" && module.exports) module.exports = { Api };
