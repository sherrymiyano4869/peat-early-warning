"""Lapisan baca untuk API v1: memecah berkas keluaran pipeline (webmap/data) menjadi sumber daya bernama.

Tidak menghitung ulang apa pun. Angka diambil apa adanya dari keluaran 09, 10, dan 20; hanya dipilah, diberi id, dan disaring.
Dipakai bersama oleh api/app.py (server) dan scripts/21_export_api.py (cermin statis) supaya bentuk responsnya sama.
Pola URL mengikuti OGC API - Features: /collections/{id}/items dan /collections/{id}/items/{featureId}.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

# Berkas -> skrip yang membuatnya, untuk pesan galat 503
SOURCE_SCRIPT = {"manifest.json": "09_export_web.py", "response.json": "20_export_response.py"}


class MissingData(Exception):
    """Berkas keluaran pipeline yang dibutuhkan belum ada."""

    def __init__(self, rel: str):
        self.rel = rel
        script = SOURCE_SCRIPT.get(rel, "09_export_web.py")
        super().__init__(f"webmap/data/{rel} belum ada. Jalankan python scripts/{script}.")


class NotFound(Exception):
    """Koleksi atau item tidak ada."""


class BadRequest(Exception):
    """Parameter kueri tidak sah."""


@dataclass(frozen=True)
class Collection:
    """Satu jenis sumber daya. Penyaring dibaca dari nama parameter: <prop> (sama dengan), min_<prop>, max_<prop>."""

    id: str
    title: str
    description: str
    tabs: tuple[str, ...]
    date_prop: str | None = None
    eq_props: tuple[str, ...] = ()
    min_props: tuple[str, ...] = ()
    max_props: tuple[str, ...] = ()
    allowed_params: frozenset[str] = field(init=False)

    def __post_init__(self) -> None:
        names = {"limit", "offset", "bbox"} | set(self.eq_props)
        names |= {f"min_{p}" for p in self.min_props} | {f"max_{p}" for p in self.max_props}
        if self.date_prop:
            names |= {"datetime", "days"}
        object.__setattr__(self, "allowed_params", frozenset(names))


COLLECTIONS: dict[str, Collection] = {c.id: c for c in (
    Collection("stations", "Stasiun muka air SiTMAT", "Muka air terakhir dan prakiraan per stasiun.", ("monitoring", "prediction"), eq_props=("region",)),
    Collection("hotspots", "Titik api VIIRS", "Titik api teramati (NASA FIRMS, Suomi NPP 375 m), tanggal WIB.", ("monitoring",),
               date_prop="date", eq_props=("dn",), min_props=("conf", "frp")),
    Collection("fire-cells", "Peluang titik api per sel 1 km", "Sel teratas peluang titik api 1 dan 3 hari (model 14).", ("prediction", "response"),
               min_props=("p1", "p3"), max_props=("rank",)),
    Collection("dryness-cells", "Prakiraan pengeringan per sel", "Peluang dan median penurunan muka air 7 dan 14 hari (model 15).", ("prediction",),
               min_props=("p7", "p14")),
    Collection("events", "Buku besar kejadian sel-hari", "Sel-hari 1 km menurut sumber bukti (satelit, laporan, keduanya) dari skrip 17.", ("response",),
               date_prop="date", eq_props=("sumber", "status", "tingkat")),
    Collection("tasks", "Tugas pemeriksaan", "Tugas terbitan terakhir: kode dan lokasi saja, tanpa alasan atau peluang.", ("response",),
               eq_props=("hasil", "status_lapangan")),
    Collection("canal-blocks", "Sekat kanal", "Kondisi sekat terakhir per titik dari laporan lapangan.", ("response",),
               date_prop="tanggal", eq_props=("kondisi",)),
    Collection("field-water-levels", "Muka air lapangan", "Bacaan muka air lapangan terakhir per titik.", ("response",), date_prop="tanggal"),
)}

TaskStatusFn = Callable[[], dict[str, dict]]


def _bbox(geom: dict) -> tuple[float, float, float, float]:
    c = geom["coordinates"]
    pts = [c] if geom["type"] == "Point" else [p for ring in c for p in ring]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _feature(fid: str, geom: dict, props: dict) -> dict:
    return {"type": "Feature", "id": fid, "geometry": geom, "properties": props}


def _polygon(ring: list) -> dict:
    return {"type": "Polygon", "coordinates": [ring]}


def _cell_id_from_ring(ring: list) -> str:
    """Cadangan untuk keluaran 14/15 lama yang belum menyimpan cell_id."""
    from src.grid import cell_id_from_ring
    return str(cell_id_from_ring(ring))


def parse_interval(text: str) -> tuple[date | None, date | None]:
    """'2026-11-01/2026-11-08', '2026-11-01/..', '../2026-11-08', atau satu tanggal."""
    parts = text.split("/")
    if len(parts) > 2:
        raise BadRequest("datetime harus satu tanggal atau rentang 'awal/akhir'.")
    try:
        ends = [None if p in ("", "..") else date.fromisoformat(p[:10]) for p in parts]
    except ValueError as e:
        raise BadRequest(f"datetime tidak sah: {text}") from e
    return (ends[0], ends[0]) if len(ends) == 1 else (ends[0], ends[1])


class DataStore:
    """Membaca webmap/data dengan cache per berkas (dibaca ulang bila waktu ubah atau ukurannya berubah)."""

    def __init__(self, data_dir: Path, task_status: TaskStatusFn | None = None):
        self.data_dir = Path(data_dir)
        self.task_status = task_status
        self._cache: dict[str, tuple[tuple[int, int], object]] = {}

    def _json(self, rel: str):
        f = self.data_dir / rel
        try:
            st = f.stat()
        except FileNotFoundError as e:
            raise MissingData(rel) from e
        key = (st.st_mtime_ns, st.st_size)
        hit = self._cache.get(rel)
        if hit is None or hit[0] != key:
            hit = (key, json.loads(f.read_text(encoding="utf-8")))
            self._cache[rel] = hit
        return hit[1]

    def manifest(self) -> dict:
        return self._json("manifest.json")

    def response(self) -> dict:
        return self._json("response.json")

    def _manifest_file(self, block: str) -> dict:
        b = self.manifest().get(block)
        if not b:
            raise MissingData(f"manifest.json:{block}")
        return self._json(b["file"])

    # ---- koleksi: daftar fitur lengkap ber-id dan metadata tingkat koleksi
    def features(self, cid: str) -> tuple[list[dict], dict]:
        if cid not in COLLECTIONS:
            raise NotFound(f"koleksi '{cid}' tidak ada")
        return getattr(self, "_f_" + cid.replace("-", "_"))()

    def _f_stations(self):
        m = self.manifest()
        gj = self._json(m["stations"]["file"])
        return [_feature(str(f["properties"]["id"]), f["geometry"], f["properties"]) for f in gj["features"]], \
            {"data_through": m.get("data_through"), "issue_date": m.get("issue_date")}

    def _f_hotspots(self):
        gj = self._manifest_file("hotspots")
        feats = []
        for f in gj["features"]:
            p, (lon, lat) = f["properties"], f["geometry"]["coordinates"]
            feats.append(_feature(f"{p['date']}_{p.get('dn') or 'x'}_{lon:.5f}_{lat:.5f}", f["geometry"], p))
        h = self.manifest()["hotspots"]
        return feats, {"date_max": h.get("date_max"), "days": h.get("days"), "note": h.get("note")}

    def _cells_geojson(self, gj: dict) -> list[dict]:
        out = []
        for f in gj["features"]:
            p, ring = f["properties"], f["geometry"]["coordinates"][0]
            cid = str(p.get("cell_id") or _cell_id_from_ring(ring))
            out.append(_feature(cid, f["geometry"], {"cell_id": cid, **{k: v for k, v in p.items() if k != "cell_id"}}))
        return out

    def _f_fire_cells(self):
        gj = self._manifest_file("fire")
        return self._cells_geojson(gj), {k: gj.get(k) for k in ("issue_date", "horizons", "top_fraction")}

    def _f_dryness_cells(self):
        gj = self._manifest_file("dryness")
        return self._cells_geojson(gj), {"issue_date": gj.get("issue_date")}

    def _f_events(self):
        r = self.response()
        feats = [_feature(f"{row['cell_id']}_{row['date']}", _polygon(r["cells"][row["cell_id"]]), row) for row in r["ledger"]]
        return feats, {k: r.get(k) for k in ("date_min", "date_max", "tiruan", "parameter")}

    def _f_tasks(self):
        r = self.response()
        status = self.task_status() if self.task_status else {}
        feats = []
        for t in r["tasks"]["items"]:
            s = status.get(t["id_tugas"], {})
            props = {**t, "status_lapangan": s.get("status", "belum"), "dikunjungi_pada": s.get("dikunjungi_pada"), "diperbarui_pada": s.get("dicatat_pada")}
            feats.append(_feature(t["id_tugas"], _polygon(r["cells"][t["cell_id"]]), props))
        return feats, {"issue_date": r["tasks"]["issue_date"], "tiruan": r.get("tiruan")}

    def _points(self, rows: list[dict]) -> list[dict]:
        return [_feature(str(x["titik"]), {"type": "Point", "coordinates": [x["lon"], x["lat"]]},
                         {k: v for k, v in x.items() if k not in ("lon", "lat")}) for x in rows]

    def _f_canal_blocks(self):
        r = self.response()
        return self._points(r["sekat"]), {"tiruan": r.get("tiruan")}

    def _f_field_water_levels(self):
        r = self.response()
        return self._points(r["water"]), {"tiruan": r.get("tiruan")}

    # ---- kueri
    def query(self, cid: str, params: dict[str, str]) -> dict:
        spec = COLLECTIONS.get(cid)
        if spec is None:
            raise NotFound(f"koleksi '{cid}' tidak ada")
        unknown = set(params) - spec.allowed_params
        if unknown:
            raise BadRequest(f"parameter tidak dikenal untuk '{cid}': {', '.join(sorted(unknown))}. Yang sah: {', '.join(sorted(spec.allowed_params))}")
        limit, offset = self._int(params, "limit", 10_000, 1, 100_000), self._int(params, "offset", 0, 0, None)
        feats, extra = self.features(cid)
        keep = self._predicate(spec, params, feats)
        if keep:
            feats = [f for f in feats if keep(f)]
        page = feats[offset:offset + limit]
        return {"type": "FeatureCollection", **extra, "numberMatched": len(feats), "numberReturned": len(page), "features": page}

    def item(self, cid: str, fid: str) -> dict:
        feats, _ = self.features(cid)
        hit = next((f for f in feats if f["id"] == fid), None)
        if hit is None:
            raise NotFound(f"item '{fid}' tidak ada di koleksi '{cid}'")
        return hit

    @staticmethod
    def _int(params: dict, key: str, default: int, lo: int, hi: int | None) -> int:
        if key not in params:
            return default
        try:
            v = int(params[key])
        except ValueError as e:
            raise BadRequest(f"{key} harus bilangan bulat") from e
        if v < lo or (hi is not None and v > hi):
            raise BadRequest(f"{key} di luar rentang [{lo}, {hi or '∞'}]")
        return v

    def _predicate(self, spec: Collection, params: dict, feats: list[dict]) -> Callable[[dict], bool] | None:
        """Mengurai parameter sekali, lalu mengembalikan penyaring per fitur (None bila tidak ada penyaring)."""
        tests: list[Callable[[dict], bool]] = []
        for k in spec.eq_props:
            if k in params:
                tests.append(lambda f, k=k, v=params[k]: str(f["properties"].get(k)) == v)
        for prefix, props, ge in (("min_", spec.min_props, True), ("max_", spec.max_props, False)):
            for k in props:
                if prefix + k not in params:
                    continue
                try:
                    lim = float(params[prefix + k])
                except ValueError as e:
                    raise BadRequest(f"{prefix + k} harus angka") from e
                tests.append(lambda f, k=k, lim=lim, ge=ge: f["properties"].get(k) is not None
                             and (float(f["properties"][k]) >= lim if ge else float(f["properties"][k]) <= lim))
        if spec.date_prop and ("datetime" in params or "days" in params):
            day = lambda f: date.fromisoformat(str(f["properties"][spec.date_prop])[:10])
            lo, hi = parse_interval(params["datetime"]) if "datetime" in params else (None, None)
            if "days" in params and feats:
                start = max(map(day, feats)) - timedelta(days=self._int(params, "days", 0, 1, 3650) - 1)
                lo = max(lo, start) if lo else start
            tests.append(lambda f: not ((lo and day(f) < lo) or (hi and day(f) > hi)))
        if "bbox" in params:
            try:
                x0, y0, x1, y1 = (float(v) for v in params["bbox"].split(","))
            except ValueError as e:
                raise BadRequest("bbox harus 'minlon,minlat,maxlon,maxlat'") from e

            def in_box(f: dict) -> bool:
                a = _bbox(f["geometry"])
                return not (a[0] > x1 or a[2] < x0 or a[1] > y1 or a[3] < y0)
            tests.append(in_box)
        return (lambda f: all(t(f) for t in tests)) if tests else None

    # ---- sumber daya non-fitur
    def series(self, station_id: str, days: int | None = None) -> dict:
        m = self.manifest()
        ids = {str(f["properties"]["id"]) for f in self._json(m["stations"]["file"])["features"]}
        if station_id not in ids:
            raise NotFound(f"stasiun '{station_id}' tidak ada")
        s = dict(self._json(m["stations"]["series_dir"] + station_id + ".json"))
        if days:
            s["dates"], s["wl_cm"] = s["dates"][-days:], s["wl_cm"][-days:]
        return s

    def meta(self) -> dict:
        m = self.manifest()
        keys = ("title", "version", "generated_at", "data_through", "issue_date", "center", "basemap", "attribution", "disclaimer", "drivers")
        try:
            r = self.response()
            resp = {k: r.get(k) for k in ("version", "generated_at", "tiruan", "date_min", "date_max")}
        except MissingData:
            resp = None
        return {**{k: m.get(k) for k in keys}, "response": resp, "collections": self.collections()["collections"]}

    def collections(self) -> dict:
        out = []
        for c in COLLECTIONS.values():
            try:
                self.features(c.id)
                ok = True
            except MissingData:
                ok = False
            out.append({"id": c.id, "title": c.title, "description": c.description, "tabs": list(c.tabs), "available": ok,
                        "queryables": sorted(c.allowed_params), "links": [{"rel": "items", "href": f"/v1/collections/{c.id}/items"}]})
        return {"collections": out}

    def susceptibility(self) -> dict:
        k = self.manifest().get("kerawanan")
        if not k:
            raise MissingData("kerawanan.json")
        return {"base_url": "/data/", **k}

    def layers(self) -> dict:
        return {"base_url": "/data/", "layers": self.manifest().get("layers", [])}

    def validation(self) -> dict:
        m = self.manifest()
        strip = lambda b: None if not b else {k: v for k, v in b.items() if k != "file"}
        return {"station_forecast": m.get("validation"), "fire": strip(m.get("fire")), "dryness": strip(m.get("dryness"))}

    def scores(self) -> dict:
        r = self.response()
        return {"tiruan": r.get("tiruan"), "scores": r.get("scores")}
