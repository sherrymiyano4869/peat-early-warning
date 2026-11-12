"""Uji alur partisipatif 19 -> 16 -> 17 -> 18 pada dunia TIRUAN kecil (folder sementara; data proyek tidak disentuh).

    python tests/test_participatory.py

Memeriksa: (1) Kobo tiruan berhalaman: semua baris terambil, token terkirim, kolom identitas dibuang; (2) 16: baris rusak dibuang, duplikat antar-potret hilang;
(3) 17: aturan tingkat A/B/C, nihil, konflik, dan kejadian yang lolos dari VIIRS; (4) 19: daftar tugas berulang sama dan berkas pemeriksa tanpa alasan;
(5) 18: hanya terbitan berjendela lengkap dinilai, model tiruan yang informatif mengalahkan klimatologi, muka air tiruan berkorelasi negatif dengan indeks.
Ini menguji ALUR dan ATURAN, bukan kinerja pada data nyata, dan Kobo tiruan bukan server Kobo.
"""
import importlib.util
import json
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import src.common as common  # noqa: E402
from src.grid import bbox_to_grid, cell_center_lonlat, grid_crs, lonlat_to_cell  # noqa: E402


def load(rel: str):
    spec = importlib.util.spec_from_file_location(Path(rel).stem.replace(".", "_"), ROOT / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run(mod, *argv):
    sys.argv = [mod.__name__, *map(str, argv)]
    mod.main()


def fake_world(tmp: Path, rng) -> dict:
    grid = tmp / "features" / "grid"
    grid.mkdir(parents=True)
    transform, (H, W), _ = bbox_to_grid((103.5, -1.7, 103.7, -1.5), 100)
    risk = np.clip(np.linspace(0, 1, W)[None, :] + rng.normal(0, 0.05, (H, W)), 0, 1).astype("float32")      # naik ke timur
    with rasterio.open(grid / "risk_index.tif", "w", driver="GTiff", height=H, width=W, count=1, dtype="float32", crs=grid_crs(), transform=transform, nodata=np.nan) as dst:
        dst.write(risk, 1)

    lon, lat = np.meshgrid(np.linspace(103.51, 103.69, 18), np.linspace(-1.69, -1.51, 18))
    cx, cy, cid = lonlat_to_cell(lon.ravel(), lat.ravel())
    cells = pd.DataFrame({"cell_id": cid, "cx": cx, "cy": cy}).drop_duplicates("cell_id").reset_index(drop=True)
    cells["lon"], cells["lat"] = cell_center_lonlat(cells["cx"], cells["cy"])
    rate = 0.002 + 0.06 * rng.random(len(cells)) ** 6                                                           # sedikit sel sangat rawan
    days = pd.date_range("2025-07-01", "2025-10-28", freq="D")
    fire = rng.random((len(days), len(cells))) < rate
    t, c = np.nonzero(fire)
    hot = pd.DataFrame({"lon": cells["lon"].to_numpy()[c] + rng.normal(0, 0.001, len(c)), "lat": cells["lat"].to_numpy()[c] + rng.normal(0, 0.001, len(c)), "date": days[t],
                        "datetime_utc": days[t] + pd.Timedelta(hours=6), "frp": 5.0, "conf": 1, "cell_id": cells["cell_id"].to_numpy()[c]})
    (tmp / "interim").mkdir()
    hot.to_parquet(tmp / "interim" / "hotspots.parquet", index=False)
    hot.groupby(["cell_id", "date"]).size().rename("n").reset_index().to_parquet(tmp / "features" / "fire_cell_day.parquet", index=False)

    issues = days[30:-1:3]                                                                                      # terbitan terakhir: jendela h=3 belum lengkap
    for k, issue in enumerate(issues):
        p1 = np.clip(rate * np.exp(rng.normal(0, 0.4, len(cells))), 0, 1)
        prob = cells.assign(p1=p1, p1_klim=rate.mean(), p3=1 - (1 - p1) ** 3, p3_klim=1 - (1 - rate.mean()) ** 3, issue_date=str(issue.date()))
        prob["rank"] = prob["p1"].rank(ascending=False, method="first").astype(int)
        folder = tmp / "outputs" / "arsip" / f"run{k:03d}"
        folder.mkdir(parents=True)
        prob.to_parquet(folder / f"fire_prob_{issue.date()}.parquet", index=False)
    return {"hot": hot, "cells": cells, "issues": issues, "fire": fire, "days": days}


def test_kobo_mock(m16) -> None:
    seen = {}

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            seen["auth"] = self.headers.get("Authorization")
            port = self.server.server_address[1]
            page = {"results": [{"_uuid": "a", "_submitted_by": "nama_akun", "jenis": "api"}], "next": f"http://127.0.0.1:{port}/page2"} if "page2" not in self.path \
                else {"results": [{"_uuid": "b", "deviceid": "x", "jenis": "nihil"}], "next": None}
            body = json.dumps(page).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    rows = m16.fetch_kobo(f"http://127.0.0.1:{srv.server_address[1]}", "UID", "rahasia")
    srv.shutdown()
    assert [r["_uuid"] for r in rows] == ["a", "b"] and seen["auth"] == "Token rahasia"
    assert not any(k in r for r in rows for k in ("_submitted_by", "deviceid"))
    print("LOLOS Kobo tiruan: 2 halaman, token terkirim, identitas dibuang")


def main() -> None:
    rng = np.random.default_rng(3)
    tmp = Path(tempfile.mkdtemp(prefix="partisipatif_"))
    common.load_config = lambda: {"paths": {k: str(tmp / k) for k in ("raw", "interim", "features", "outputs")}}
    m16, m17, m18, m19, fake = (load(f) for f in ("scripts/16_ingest_reports.py", "scripts/17_event_ledger.py", "scripts/18_score_prospective.py",
                                                  "scripts/19_verification_tasks.py", "tools/fake_reports.py"))
    test_kobo_mock(m16)
    w = fake_world(tmp, rng)
    hot, issues = w["hot"], w["issues"]

    # ---- 19: tugas untuk beberapa terbitan; berulang sama; berkas pemeriksa tanpa alasan dan peluang
    for issue in issues[:12]:
        src = next((tmp / "outputs" / "arsip").glob(f"*/fire_prob_{issue.date()}.parquet"))
        (tmp / "outputs" / "fire_prob_latest.parquet").write_bytes(src.read_bytes())
        run(m19, "--n-top", 15, "--n-random", 15)
    first = pd.read_parquet(tmp / "outputs" / "tugas" / f"tugas_{issues[11].date()}.parquet")
    run(m19, "--n-top", 15, "--n-random", 15)
    assert first.equals(pd.read_parquet(tmp / "outputs" / "tugas" / f"tugas_{issues[11].date()}.parquet"))
    assert first["alasan"].value_counts().to_dict() == {"teratas": 15, "acak": 15} and first["id_tugas"].is_unique
    props = json.loads((tmp / "outputs" / "verification_tasks.geojson").read_text())["features"][0]["properties"]
    assert set(props) == {"id_tugas", "lon", "lat"}
    print("LOLOS 19: daftar tugas deterministik, berkas pemeriksa buta")

    # ---- 16: laporan tiruan + baris buatan tangan untuk menguji aturan
    csv = tmp / "tiruan.csv"
    run(fake, "--out", csv)
    n_fake = len(pd.read_csv(csv))
    h = hot.iloc[0]
    far = dict(lokasi="-1.2000 103.9000 0 5")                       # di luar area titik api tiruan
    hand = pd.DataFrame([
        dict(_uuid="A-cocok", waktu_amat=f"{h.datetime_utc.isoformat()}Z", lokasi=f"{h.lat} {h.lon} 0 90", jenis="api", pelapor="warga", kode_pelapor="X1"),
        dict(_uuid="A-petugas", waktu_amat="2025-08-01T03:00:00Z", lokasi="-1.2000 103.9000 0 5", jenis="membara", pelapor="bpbd", kode_pelapor="X2", foto="f.jpg"),
        dict(_uuid="B-foto", waktu_amat="2025-08-02T03:00:00Z", **far, jenis="asap", pelapor="warga", kode_pelapor="X3", foto="f.jpg"),
        dict(_uuid="C-sendiri", waktu_amat="2025-08-03T03:00:00Z", **far, jenis="api", pelapor="warga", kode_pelapor="X3"),
        dict(_uuid="B-dua-1", waktu_amat="2025-08-04T03:00:00Z", **far, jenis="api", pelapor="warga", kode_pelapor="X3"),
        dict(_uuid="B-dua-2", waktu_amat="2025-08-04T05:00:00Z", **far, jenis="asap", pelapor="mpa", kode_pelapor="X4"),
        dict(_uuid="C-gps", waktu_amat="2025-08-05T03:00:00Z", lokasi="-1.2000 103.9000 0 400", jenis="api", pelapor="bpbd", kode_pelapor="X2", foto="f.jpg"),
        dict(_uuid="B-telat", waktu_amat="2025-08-06T03:00:00Z", _submission_time="2025-08-20T03:00:00Z", **far, jenis="api", pelapor="bpbd", kode_pelapor="X2", foto="f.jpg"),
        dict(_uuid="nihil-A", waktu_amat="2025-08-07T03:00:00Z", **far, jenis="nihil", pelapor="manggala_agni", kode_pelapor="X5", foto="f.jpg"),
        dict(_uuid="nihil-konflik", waktu_amat=f"{h.datetime_utc.isoformat()}Z", lokasi=f"{h.lat} {h.lon} 0 5", jenis="nihil", pelapor="warga", kode_pelapor="X6"),
        dict(_uuid="buang-gps0", waktu_amat="2025-08-08T03:00:00Z", lokasi="0 0 0 5", jenis="api", pelapor="warga"),
        dict(_uuid="buang-jenis", waktu_amat="2025-08-08T03:00:00Z", **far, jenis="lainnya", pelapor="warga"),
        dict(_uuid="buang-air", waktu_amat="2025-08-08T03:00:00Z", **far, jenis="muka_air", pelapor="warga"),
        dict(_uuid="buang-depan", waktu_amat="2100-01-01T00:00:00Z", **far, jenis="api", pelapor="warga"),
    ])
    hand.to_csv(tmp / "uji.csv", index=False)
    run(m16, "--csv", csv, "--source", "tiruan")
    run(m16, "--csv", tmp / "uji.csv", "--source", "uji")
    run(m16, "--csv", csv, "--source", "tiruan")                    # potret kedua yang sama: tidak boleh menggandakan
    rep = pd.read_parquet(tmp / "interim" / "reports.parquet")
    assert len(rep) == n_fake + 10 and rep["report_id"].is_unique, (len(rep), n_fake)
    assert not rep["report_id"].str.startswith("buang").any()
    assert (rep.set_index("report_id").loc[["C-gps", "B-telat"], ["flag_gps", "flag_delay"]].to_numpy() == [[True, False], [False, True]]).all()
    assert len(list((tmp / "raw" / "laporan").glob("*/*.gz"))) == 3 and len((tmp / "raw" / "laporan" / "manifest.jsonl").read_text().splitlines()) == 3
    print(f"LOLOS 16: {len(rep)} laporan, 4 baris rusak dibuang, potret ganda tidak menggandakan")

    # ---- 17: aturan tingkat
    run(m17)
    led = pd.read_parquet(tmp / "features" / "event_ledger.parquet")
    at = lambda rid: led.merge(rep.loc[rep["report_id"] == rid, ["cell_id", "date"]], on=["cell_id", "date"]).iloc[0]
    for rid, tingkat, sumber, y_buku in (("A-cocok", "A", "keduanya", 1), ("A-petugas", "A", "laporan", 1), ("B-foto", "B", "laporan", 1), ("C-sendiri", "C", "laporan", 0),
                                         ("B-dua-1", "B", "laporan", 1), ("C-gps", "C", "laporan", 0), ("B-telat", "B", "laporan", 1)):
        r = at(rid)
        assert (r["tingkat"], r["sumber"], r["y_buku"], r["status"]) == (tingkat, sumber, y_buku, "kejadian"), (rid, dict(r))
    r = at("nihil-A")
    assert (r["status"], r["tingkat"], r["y_lapangan"], r["y_buku"]) == ("nihil", "A", 0.0, 0)
    r = at("nihil-konflik")
    assert r["konflik"] and r["status"] == "kejadian" and r["y_viirs"] == 1
    assert at("A-petugas")["membara"] and at("A-petugas")["n_viirs"] == 0
    assert led.groupby(["cell_id", "date"]).ngroups == len(led)
    assert (led["y_viirs"] == 1).sum() == hot.groupby(["cell_id", "date"]).ngroups                      # semua sel-hari VIIRS masuk buku besar
    meta = json.loads((tmp / "interim" / "ledger_meta.json").read_text())
    assert meta["lolos_dari_viirs"] > 0 and meta["berisi_data_tiruan"]
    sekat = pd.read_parquet(tmp / "features" / "canal_blocks.parquet")
    assert sekat["titik"].is_unique and len(sekat) == 15
    print(f"LOLOS 17: tingkat A/B/C, nihil, konflik; lolos dari VIIRS {meta['lolos_dari_viirs']} dari {meta['kejadian_lapangan_AB']} kejadian lapangan")

    # ---- 18
    run(m18, "--min-issues", 10)
    res = json.loads((tmp / "outputs" / "prospective_scores.json").read_text())
    assert res["berisi_data_tiruan"] and res["arsip_terbitan"] == len(issues) and res["terbitan_horizon_belum_lengkap"] == 1
    h1, h3 = res["titik_api"]["h1"], res["titik_api"]["h3"]
    assert h1["viirs"]["n_terbitan"] == len(issues) and h3["viirs"]["n_terbitan"] == len(issues) - 1
    cells, fire, days = w["cells"], w["fire"], w["days"]
    expect = sum(int(fire[days.get_loc(i) + 1].sum()) for i in issues)                                    # hitung ulang mandiri: sel berapi pada t+1
    assert h1["viirs"]["n_positif"] == expect, (h1["viirs"]["n_positif"], expect)
    assert h1["viirs"]["pr_auc_model"] > h1["viirs"]["pr_auc_klimatologi"] and h1["lolos_prospektif"]
    assert h1["buku"]["n_positif"] >= h1["viirs"]["n_positif"] and h1["n_sel_bertindakan"] > 0
    assert h1["viirs_tanpa_sel_bertindakan"]["n_sel_terbitan"] == h1["viirs"]["n_sel_terbitan"] - h1["n_sel_bertindakan"]
    tugas = res["tugas_pemeriksaan"]["per_alasan"]
    assert tugas["teratas"]["tugas"] == tugas["acak"]["tugas"] == 180 and 0 < tugas["teratas"]["diperiksa"] < 180
    assert tugas["teratas"]["laju_kejadian"] > tugas["acak"]["laju_kejadian"]
    air = res["muka_air_vs_indeks"]
    assert air["n_titik_dipakai"] == 25 and air["spearman_rho"] < 0 and air["selang_95"][1] < 0, air
    by = pd.read_csv(tmp / "outputs" / "prospective_by_issue.csv")
    assert set(by["horizon"]) == {1, 3} and (by["n_sel"] == len(cells)).all()
    print("LOLOS 18: jendela lengkap saja, positif cocok dengan hitungan mandiri, tugas dan muka air terbaca")
    print("\nSEMUA LOLOS (alur dan aturan pada data tiruan; bukan bukti kinerja)")


if __name__ == "__main__":
    main()
