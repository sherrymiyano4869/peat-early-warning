"""Uji API v1 dan cermin statisnya pada webmap/data tiruan di folder sementara.

    python tests/test_api.py      (atau pytest tests/test_api.py)

Memeriksa: bentuk koleksi, penyaring terhadap hitungan mandiri, id sel cadangan untuk keluaran 14/15 lama, galat 400/404/503,
PATCH tugas (token, aturan waktu, tambah-saja), dan kesamaan cermin statis dengan respons server.
"""
import importlib.util
import json
import sqlite3
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from api.app import create_app
from src.grid import cell_id, cell_polygon_lonlat, lonlat_to_cell

TOKEN = "uji-token"
ISSUE = "2026-11-10"


def _dump(f: Path, obj) -> None:
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(obj), encoding="utf-8")


def fake_data(d: Path, with_cell_id: bool) -> dict:
    """webmap/data minimal dengan bentuk yang sama seperti keluaran 09 dan 20."""
    cx0, cy0, _ = lonlat_to_cell([103.93], [-1.31])
    cells = [(int(cx0[0]) + i, int(cy0[0]) + j) for i in range(4) for j in range(3)]
    ids = [str(int(cell_id(a, b))) for a, b in cells]
    ring = {i: cell_polygon_lonlat(a, b) for i, (a, b) in zip(ids, cells)}

    def cellfeat(i, props):
        return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring[i]]},
                "properties": ({"cell_id": i} if with_cell_id else {}) | props}

    stations = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [103.9 + k / 100, -1.3]},
                 "properties": {"id": f"S{k}", "region": "Jambi" if k < 2 else "Riau", "wl_last_cm": -30.0 - k}} for k in range(3)]
    for k in range(3):
        _dump(d / "series" / f"S{k}.json", {"id": f"S{k}", "dates": [f"2026-11-0{n}" for n in range(1, 10)], "wl_cm": list(range(9))})
    hot = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [103.95 + k / 1000, -1.30]},
            "properties": {"date": f"2026-11-{1 + k:02d}", "frp": 2.0 * k, "conf": 50 + k, "dn": "N" if k % 2 else "D"}} for k in range(8)]
    _dump(d / "stations.geojson", {"type": "FeatureCollection", "features": stations})
    _dump(d / "hotspots_recent.geojson", {"type": "FeatureCollection", "features": hot})
    _dump(d / "fire_cells.geojson", {"type": "FeatureCollection", "issue_date": ISSUE, "horizons": [1, 3], "top_fraction": 0.05,
                                     "features": [cellfeat(i, {"rank": r + 1, "p1": round(0.3 - r / 50, 4), "p3": 0.4}) for r, i in enumerate(ids[:6])]})
    _dump(d / "dry_cells.geojson", {"type": "FeatureCollection", "issue_date": ISSUE,
                                    "features": [cellfeat(i, {"p7": r / 20, "p14": r / 12, "d7": -1.0, "d14": -2.0, "q10_14": -5.0, "q90_14": 1.0}) for r, i in enumerate(ids)]})
    _dump(d / "manifest.json", {
        "title": "uji", "version": "v0.22", "generated_at": "2026-11-16T00:00:00Z", "data_through": "2026-11-09", "issue_date": ISSUE,
        "center": [-1.31, 103.93], "basemap": None, "attribution": ["OSM"], "disclaimer": "uji", "drivers": [], "layers": [],
        "validation": {"available": False}, "stations": {"file": "stations.geojson", "n": 3, "series_dir": "series/"},
        "kerawanan": {"levels": [{"url": "tiles/kerawanan/{z}/{x}/{y}.png"}]},
        "hotspots": {"file": "hotspots_recent.geojson", "n": 8, "days": 8, "date_max": "2026-11-08", "note": ""},
        "fire": {"file": "fire_cells.geojson", "issue_date": ISSUE, "skill_ok": False, "cap_class": 0},
        "dryness": {"file": "dry_cells.geojson", "issue_date": ISSUE, "skill_ok": False, "cap_class": 0}})
    ledger = [{"cell_id": ids[k % 5], "date": f"2026-11-{1 + k:02d}", "status": "kejadian" if k % 3 else "nihil",
               "sumber": ["satelit", "laporan", "keduanya"][k % 3], "tingkat": "A" if k % 2 else "B"} for k in range(10)]
    tasks = [{"id_tugas": f"T20261110-{k:03d}", "cell_id": ids[k], "hasil": "belum" if k else "nihil"} for k in range(1, 4)]
    _dump(d / "response.json", {
        "version": "v0.22", "generated_at": "2026-11-16T00:00:00Z", "tiruan": True, "date_min": "2026-11-01", "date_max": "2026-11-10",
        "parameter": {"radius_m": 1000}, "cells": ring, "ledger": ledger, "tasks": {"issue_date": ISSUE, "items": tasks},
        "top_cells": None, "water": [{"titik": "W1", "lon": 103.9, "lat": -1.3, "muka_air_cm": -45.0, "tanggal": "2026-11-05", "n": 2}],
        "sekat": [{"titik": "K1", "lon": 103.91, "lat": -1.31, "kondisi": "rusak", "tanggal": "2026-11-04", "n": 1}],
        "scores": {"n_terbitan": 3, "lolos_prospektif": False}})
    return {"ids": ids, "ledger": ledger, "hot": hot}


def client(tmp: Path, with_cell_id: bool = True, token: str = TOKEN):
    data = tmp / "web" / "data"
    world = fake_data(data, with_cell_id)
    return TestClient(create_app(data_dir=data, db_path=tmp / "tasks.sqlite", web_dir=tmp / "web", token=token)), world


def test_read(tmp_path: Path) -> None:
    tmp = tmp_path
    c, w = client(tmp)
    cols = c.get("/v1/collections").json()["collections"]
    assert {x["id"] for x in cols} == {"stations", "hotspots", "fire-cells", "dryness-cells", "events", "tasks", "canal-blocks", "field-water-levels"}
    assert all(x["available"] for x in cols)
    r = c.get("/v1/collections/hotspots/items")
    assert r.headers["content-type"].startswith("application/geo+json") and r.json()["numberMatched"] == 8
    # penyaring vs hitungan mandiri
    exp = sum(1 for f in w["hot"] if f["properties"]["date"] >= "2026-11-06")
    assert c.get("/v1/collections/hotspots/items", params={"days": 3}).json()["numberMatched"] == exp
    assert c.get("/v1/collections/hotspots/items", params={"datetime": "2026-11-06/.."}).json()["numberMatched"] == exp
    exp = sum(1 for f in w["hot"] if f["properties"]["conf"] >= 53 and f["properties"]["dn"] == "N")
    assert c.get("/v1/collections/hotspots/items", params={"min_conf": 53, "dn": "N"}).json()["numberMatched"] == exp
    exp = sum(1 for x in w["ledger"] if x["sumber"] == "laporan" and "2026-11-03" <= x["date"] <= "2026-11-08")
    assert c.get("/v1/collections/events/items", params={"sumber": "laporan", "datetime": "2026-11-03/2026-11-08"}).json()["numberMatched"] == exp
    assert c.get("/v1/collections/fire-cells/items", params={"max_rank": 3}).json()["numberMatched"] == 3
    p = c.get("/v1/collections/stations/items", params={"limit": 1, "offset": 1}).json()
    assert p["numberMatched"] == 3 and p["numberReturned"] == 1 and p["features"][0]["id"] == "S1"
    assert c.get("/v1/collections/stations/items", params={"bbox": "103.905,-1.4,103.925,-1.2"}).json()["numberMatched"] == 2
    # item per sel
    cid = w["ids"][4]
    f = c.get(f"/v1/collections/dryness-cells/items/{cid}").json()
    assert f["id"] == cid and f["properties"]["cell_id"] == cid and f["properties"]["p7"] == 4 / 20
    assert c.get("/v1/stations/S1/series", params={"days": 3}).json()["dates"] == ["2026-11-07", "2026-11-08", "2026-11-09"]
    assert c.get("/v1/validation").json()["fire"] == {"issue_date": ISSUE, "skill_ok": False, "cap_class": 0}
    assert c.get("/v1/meta").json()["response"]["tiruan"] is True
    # galat
    assert c.get("/v1/collections/hotspots/items", params={"tanggal": "x"}).status_code == 400
    assert c.get("/v1/collections/hotspots/items", params={"bbox": "1,2"}).status_code == 400
    assert c.get("/v1/collections/nope/items").json()["code"] == "tidak_ditemukan"
    assert c.get("/v1/stations/..%2Fmanifest/series").status_code == 404
    (tmp / "web" / "data" / "response.json").unlink()
    r = c.get("/v1/collections/events/items")
    assert r.status_code == 503 and "20_export_response.py" in r.json()["description"]
    assert c.get("/v1/meta").json()["response"] is None


def test_cell_id_fallback(tmp_path: Path) -> None:
    """Keluaran 14/15 lama tanpa cell_id: id dari titik tengah poligon harus sama dengan id asli."""
    tmp = tmp_path
    c, w = client(tmp, with_cell_id=False)
    got = [f["id"] for f in c.get("/v1/collections/dryness-cells/items").json()["features"]]
    assert got == w["ids"]


def test_patch(tmp_path: Path) -> None:
    tmp = tmp_path
    c, _ = client(tmp)
    url, auth = "/v1/collections/tasks/items/T20261110-001", {"Authorization": f"Bearer {TOKEN}"}
    assert c.patch(url, json={"status": "dalam_perjalanan"}).status_code == 401
    assert c.patch(url, json={"status": "selesai"}, headers=auth).status_code == 400
    assert c.patch(url, json={"status": "diperiksa"}, headers=auth).status_code == 400            # tanpa waktu kunjungan
    assert c.patch(url, json={"status": "diperiksa", "dikunjungi_pada": "2026-11-09T10:00:00+07:00"}, headers=auth).status_code == 400  # sebelum terbit
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    assert c.patch(url, json={"status": "diperiksa", "dikunjungi_pada": future}, headers=auth).status_code == 400
    assert c.patch(url, json={"status": "diperiksa", "dikunjungi_pada": "2026-11-11T10:00:00"}, headers=auth).status_code == 400  # tanpa zona
    assert c.patch(url, json={"hasil": "kejadian"}, headers=auth).status_code == 400              # hasil bukan milik PATCH
    assert c.patch("/v1/collections/tasks/items/T-tidak-ada", json={"status": "belum"}, headers=auth).status_code == 404
    r = c.patch(url, json={"status": "dalam_perjalanan"}, headers=auth)
    assert r.status_code == 200 and r.json()["properties"]["status_lapangan"] == "dalam_perjalanan"
    r = c.patch(url, json={"status": "diperiksa", "dikunjungi_pada": "2026-11-11T10:00:00+07:00", "catatan": "akses lewat kanal"}, headers=auth)
    p = r.json()["properties"]
    assert p["status_lapangan"] == "diperiksa" and p["dikunjungi_pada"] == "2026-11-11T03:00:00Z" and p["hasil"] == "belum"
    r = c.patch(url, json={"catatan": "foto menyusul"}, headers=auth).json()["properties"]                   # PATCH sebagian
    assert r["status_lapangan"] == "diperiksa" and r["dikunjungi_pada"] == "2026-11-11T03:00:00Z"
    h = c.get(url + "/history").json()["history"]
    assert [x["status"] for x in h] == ["dalam_perjalanan", "diperiksa", "diperiksa"] and h[-1]["catatan"] == "foto menyusul"
    other = c.get("/v1/collections/tasks/items", params={"status_lapangan": "belum"}).json()
    assert other["numberMatched"] == 2
    con = sqlite3.connect(tmp / "tasks.sqlite")
    for sql in ("UPDATE task_update SET status='belum'", "DELETE FROM task_update"):
        try:
            con.execute(sql)
            raise AssertionError("tabel harus tambah-saja")
        except sqlite3.IntegrityError:
            pass
    con.close()
    c2, _ = client(tmp / "tanpa", token="")
    assert c2.patch(url, json={"status": "belum"}, headers=auth).json()["code"] == "tulis_nonaktif"


def test_static_matches_server(tmp_path: Path) -> None:
    tmp = tmp_path
    c, _ = client(tmp)
    spec = importlib.util.spec_from_file_location("m21", ROOT / "scripts" / "21_export_api.py")
    m21 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m21)
    data = tmp / "web" / "data"
    assert m21.export(data, tmp / "tasks.sqlite") == []
    for rel in ("meta", "collections", "validation", "scores", "collections/events/items", "collections/tasks/items", "stations/S2/series"):
        assert json.loads((data / "v1" / f"{rel}.json").read_text(encoding="utf-8")) == c.get(f"/v1/{rel}").json(), rel


def main() -> None:
    for t in (test_read, test_cell_id_fallback, test_patch, test_static_matches_server):
        t(Path(tempfile.mkdtemp(prefix="api_")))
        print("lolos:", t.__name__)


if __name__ == "__main__":
    main()
