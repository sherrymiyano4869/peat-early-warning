"""09_export_web: ekspor hasil ke aset statis untuk WebGIS (Leaflet): PNG hamparan, GeoJSON stasiun, deret waktu, manifest.

    python scripts/09_export_web.py [--out webmap/data] [--series-days 90]
    python -m http.server -d webmap 8000        # lalu buka http://localhost:8000

Masuk (yang ada saja):
  data/features/grid/static.tif, confidence_static.tif (07); risk.tif dan confidence_class.tif (08, nanti)
  data/features/model_table.parquet (03), data/interim/stations.parquet (01)
  outputs/predictions_latest.csv dan walkforward_summary.csv (06)
Keluar: webmap/data/manifest.json, stations.geojson, series/<id>.json, layers/<id>.png

Lapisan kerawanan tiga tingkat dibuat oleh 10_build_tiles.py (kerawanan.json ikut ditanam di manifest). Hamparan dibuat dari raster (UTM -> EPSG:4326) dengan palet warna dan batas; manifest memuat legenda, status validasi, atribusi, dan
penafian. Seluruh keluaran statis, jadi bisa dihosting di GitHub Pages atau server berkas biasa.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import rasterio
from PIL import Image
from rasterio.warp import Resampling, calculate_default_transform, reproject

matplotlib.use("Agg")
from matplotlib import colormaps  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import ROOT, load_config, path  # noqa: E402
from src.confidence import CLASS_LABEL, cap_from_skill  # noqa: E402
from src.regions import add_region  # noqa: E402

# (id, berkas raster, nama band, judul, satuan, palet, vmin, vmax (None = persentil 98), kategorikal, tampil awal)
# (id, berkas raster, nama band, judul, satuan, palet, vmin, vmax (None = persentil 98), kategorikal, tampil awal)
# Lapisan teknis hanya dengan --advanced-layers. Informasi "jauh dari stasiun / di luar AOA" sudah tersampaikan oleh transparansi dan arsiran
# kepercayaan; hillshade (10_build_tiles.py) menggantikan relief lokal.
LAYERS = [
    ("dist_station_km", "confidence_static.tif", "dist_station_km", "Jarak ke stasiun terdekat", "km", "Greys", 0, 20, False, False),
    ("outside_aoa", "confidence_static.tif", "inside_aoa", "Di luar area penerapan model (AOA)", "", None, 0, 1, True, False),
]
CATEGORICAL = {"outside_aoa": {0: (90, 90, 90, 150)}}
LEGEND_ITEMS = {"outside_aoa": [("di luar area penerapan", "#5a5a5a")]}
ATTRIBUTION = [
    "Muka air dan stasiun: SiTMAT (KLH/BRGM), diambil dengan jeda sopan; data dapat berubah atau terkoreksi.",
    "(c) OpenStreetMap contributors (ODbL); kanal dan batas gambut/KHG dari BRGM BlueBook 2026. Peta dasar: OpenStreetMap (tile standar; patuhi kebijakan tile OSM, ganti lewat manifest.basemap bila lalu lintas besar).",
    "Tutupan lahan: ESA WorldCover 10 m 2021 (CC BY 4.0).",
    "Titik api: NRT/standar VIIRS 375 m Active Fire (VNP14IMG) dari NASA LANCE/FIRMS, doi:10.5067/FIRMS/VIIRS/VNP14IMGT_NRT.002; ikuti ketentuan sitasi dan penafian NASA LANCE/FIRMS saat membagikan ulang.",
    "FABDEM is produced using Copernicus WorldDEM-30 (c) DLR e.V. (CC BY-NC-SA 4.0), Hawker dkk. 2022.",
    "Hujan: JAXA GSMaP (Global Rainfall Map in Near-Real-Time) dan CHIRPS; citra: Copernicus Sentinel-1/2.",
]
DISCLAIMER = ("Prototipe riset. Bukan peringatan resmi. Prediksi belum dikalibrasi; baca status validasi dan kelas kepercayaan "
              "sebelum memakai hasilnya.")


def read_version() -> str:
    changelog = ROOT / "CHANGELOG.md"
    if changelog.exists():
        m = re.search(r"^##\s+(v[\d.]+)", changelog.read_text(encoding="utf-8"), re.M)
        if m:
            return m.group(1)
    return "dev"


def render_layer(tif: Path, band: str, out_png: Path, cmap_name, vmin, vmax, categorical: bool, layer_id: str):
    with rasterio.open(tif) as src:
        if band not in src.descriptions:
            return None
        data = src.read(list(src.descriptions).index(band) + 1).astype("float32")
        transform, w, h = calculate_default_transform(src.crs, "EPSG:4326", src.width, src.height, *src.bounds)
        dst = np.full((h, w), np.nan, dtype="float32")
        reproject(data, dst, src_transform=src.transform, src_crs=src.crs, src_nodata=np.nan, dst_transform=transform,
                  dst_crs="EPSG:4326", dst_nodata=np.nan, resampling=Resampling.nearest if categorical else Resampling.bilinear)
    west, north = transform * (0, 0)
    east, south = transform * (w, h)
    valid = np.isfinite(dst)
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    if categorical:
        for value, color in CATEGORICAL[layer_id].items():
            rgba[valid & (np.rint(dst) == value)] = color
        legend = {"type": "categorical", "items": [{"label": l, "color": c} for l, c in LEGEND_ITEMS[layer_id]]}
        lo, hi = vmin, vmax
    else:
        hi = float(np.nanpercentile(dst[valid], 98)) if vmax is None and valid.any() else float(vmax)
        hi = hi if hi > vmin else vmin + 1.0
        lo = float(vmin)
        cmap = colormaps[cmap_name]
        norm = np.clip((np.nan_to_num(dst, nan=lo) - lo) / (hi - lo), 0, 1)
        rgba[...] = (cmap(norm) * 255).astype(np.uint8)
        rgba[~valid, 3] = 0
        legend = {"type": "continuous", "min": lo, "max": hi,
                  "colors": ["#%02x%02x%02x" % tuple(int(c * 255) for c in cmap(t)[:3]) for t in np.linspace(0, 1, 6)]}
    out_png.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, "RGBA").save(out_png, optimize=True)
    return {"bounds": [[south, west], [north, east]], "legend": legend, "size": [w, h]}


def validation_block(outputs: Path) -> dict:
    f = outputs / "walkforward_summary.csv"
    if not f.exists():
        return {"available": False, "note": "Belum ada uji walk-forward (jalankan 06_predict.py --walk-forward)."}
    sm = pd.read_csv(f).set_index("horizon")
    skills = {int(h): float(sm.loc[h, "skill_vs_persistensi"]) for h in sm.index}
    cov = {int(h): float(sm.loc[h, "cakupan_q10_q90"]) for h in sm.index}
    worst = min(skills.values())
    cap = cap_from_skill(worst)
    return {"available": True, "skill_h7": skills.get(7), "skill_h14": skills.get(14), "coverage_q10_q90_h7": cov.get(7),
            "coverage_q10_q90_h14": cov.get(14), "cap_class": cap, "cap_label": CLASS_LABEL[cap],
            "n_issue_dates": int(sm["tanggal_terbit"].max()) if "tanggal_terbit" in sm else None,
            "note": "Skill terhadap persistensi pada walk-forward mingguan; kelas kepercayaan dibatasi oleh skill terburuk."}


def export_hotspots(out: Path, days: int = 7):
    """Titik api VIIRS 7 hari terakhir (relatif terhadap tanggal data terbaru) untuk halaman Monitoring."""
    f = path("interim") / "hotspots.parquet"
    if not f.exists():
        return None
    h = pd.read_parquet(f)
    if h.empty:
        return None
    h["date"] = pd.to_datetime(h["date"])
    dmax = h["date"].max()
    recent = h[h["date"] >= dmax - pd.Timedelta(days=days - 1)]
    feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(float(r.lon), 5), round(float(r.lat), 5)]},
              "properties": {"date": str(r.date.date()), "frp": None if pd.isna(r.frp) else round(float(r.frp), 1), "conf": int(r.conf), "dn": r.daynight}}
             for r in recent.itertuples()]
    (out / "hotspots_recent.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False), encoding="utf-8")
    print(f"titik api: {len(feats)} dalam {days} hari sampai {dmax.date()}")
    return {"file": "hotspots_recent.geojson", "n": len(feats), "days": days, "date_max": str(dmax.date()),
            "note": "Tanggal WIB; satelit Suomi NPP 375 m (NASA FIRMS)."}


def export_fire(out: Path, outputs: Path):
    """Sel teratas peluang titik api dan ringkasan uji untuk halaman Prediksi."""
    gj, mj = outputs / "fire_top_cells.geojson", outputs / "fire_metrics.json"
    if not gj.exists() or not mj.exists():
        return None
    g, m = json.loads(gj.read_text(encoding="utf-8")), json.loads(mj.read_text(encoding="utf-8"))
    (out / "fire_cells.geojson").write_text(json.dumps(g, ensure_ascii=False), encoding="utf-8")
    h1 = m["horizon"].get("h1", {})
    mod, clim, per = h1.get("model", {}), h1.get("klimatologi", {}), h1.get("persistensi", {})
    pl = m.get("prediksi_terakhir", {})
    return {"file": "fire_cells.geojson", "issue_date": g.get("issue_date"), "horizons": g.get("horizons"), "top_fraction": g.get("top_fraction"),
            "n_top": len(g["features"]), "n_cells": pl.get("n_sel"), "expected_cells_h1": pl.get("harapan_sel_berapi_p1"), "primary_key": "p1",
            "skill_ok": bool(m.get("skill_ok")), "cap_class": int(m.get("cap_class", 0)),
            "metrics": {"pr_auc_model": mod.get("pr_auc"), "pr_auc_klim": clim.get("pr_auc"), "pr_auc_persist": per.get("pr_auc"),
                        "skill_brier": h1.get("skill_brier_vs_klimatologi"), "periode_uji": " s/d ".join(h1.get("periode", {}).get("uji", []))}}


def export_dryness(out: Path, outputs: Path):
    """Sel prakiraan pengeringan 7 dan 14 hari (semua sel yang dinilai) dan ringkasan uji ruang-waktu."""
    gj, mj = outputs / "dryness_cells.geojson", outputs / "dryness_metrics.json"
    if not gj.exists() or not mj.exists():
        return None
    g, m = json.loads(gj.read_text(encoding="utf-8")), json.loads(mj.read_text(encoding="utf-8"))
    (out / "dry_cells.geojson").write_text(json.dumps(g, ensure_ascii=False), encoding="utf-8")
    ev = m.get("uji_ruang_waktu", {})
    return {"file": "dry_cells.geojson", "issue_date": g.get("issue_date"), "n_cells": len(g["features"]), "skill_ok": bool(m.get("skill_ok")), "cap_class": int(m.get("cap_class", 0)),
            "n_stasiun": m.get("n_stasiun"), "p14_rata2": m.get("prediksi_terakhir", {}).get("p14_rata2"),
            "metrics": {f"h{h}": {k: ev.get(f"h{h}", {}).get(k) for k in ("skill_mae", "cakupan_q10_q90", "skill_brier", "n_uji")} for h in (7, 14)}}


def driver_status(n_stations: int, mt: pd.DataFrame, hot, dry=None) -> list:
    """Daftar masukan sistem dan statusnya, dibaca dari berkas yang benar-benar ada (bukan janji)."""
    grid = path("features") / "grid"
    feat = path("features")
    has_rain, has_soil, has_ndmi = (feat / "dyn_rain_pixels.parquet").exists(), (feat / "dyn_soil_pixels.parquet").exists(), (feat / "dyn_ndmi_cells.parquet").exists()
    dyn_cols = ({"rain_7d"} if has_rain else set()) | ({"soil_moisture"} if has_soil else set())
    enso_dir = path("raw") / "enso"
    has_enso = enso_dir.exists() and any(enso_dir.iterdir())
    cols = " ".join(map(str, mt.columns))
    rain_station = "rain" in cols
    ndmi_station = "ndmi" in cols.lower()

    def row(i, t, ok, partial=False, detail=""):
        return {"id": i, "title": t, "status": "tersedia" if ok else ("sebagian" if partial else "belum tersedia"), "detail": detail}
    return [
        row("stasiun", "Sensor muka air (SiTMAT)", n_stations > 0, detail=f"{n_stations} stasiun"),
        row("hujan", "Hujan (GSMaP, CHIRPS)", "rain_7d" in dyn_cols, rain_station, "per sel" if "rain_7d" in dyn_cols else ("di tingkat stasiun; per sel belum" if rain_station else "")),
        row("kelembapan", "Indeks kelembapan tanah", "soil_moisture" in dyn_cols, False, "ERA5-Land 0–7 cm (reanalisis, bukan pengamatan gambut)" if "soil_moisture" in dyn_cols else "belum diambil (02f --only era5soil)"),
        row("ndmi", "NDMI Sentinel-2", has_ndmi, ndmi_station, "komposit bulanan per sel" if has_ndmi else ("di tingkat stasiun; per sel belum" if ndmi_station else "")),
        row("enso", "ENSO dan IOD (DMI)", has_enso, detail="indeks bulanan" if has_enso else ""),
        row("topografi", "Topografi (FABDEM) dan kanal", (grid / "static.tif").exists(), detail="grid 100 m, grid induk equal-area"),
        row("lulc", "Tutupan lahan (WorldCover)", (grid / "lulc.tif").exists(), detail="2021, tanpa kelas sawit" if (grid / "lulc.tif").exists() else "belum diekstrak (02e)"),
        row("hotspot", "Titik api VIIRS", hot is not None, detail=f"{hot['n']} titik, sampai {hot['date_max']}" if hot else ""),
        row("kering_sel", "Prakiraan pengeringan per sel (7–14 hari)", dry is not None, detail=(f"{dry['n_cells']} sel; kepercayaan {'sedang' if dry['cap_class'] else 'rendah'}" if dry else "belum dijalankan (15)")),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(ROOT / "webmap" / "data"))
    parser.add_argument("--series-days", type=int, default=90)
    parser.add_argument("--advanced-layers", action="store_true", help="sertakan lapisan teknis (jarak ke stasiun, AOA)")
    args = parser.parse_args()
    out = Path(args.out)
    grid, outputs = path("features") / "grid", path("outputs")
    (out / "layers").mkdir(parents=True, exist_ok=True)
    (out / "series").mkdir(parents=True, exist_ok=True)

    layers = []
    for lid, fname, band, title, unit, cmap_name, vmin, vmax, categorical, default in (LAYERS if args.advanced_layers else []):
        tif = grid / fname
        if not tif.exists():
            continue
        info = render_layer(tif, band, out / "layers" / f"{lid}.png", cmap_name, vmin, vmax, categorical, lid)
        if info:
            layers.append({"id": lid, "title": title, "unit": unit, "file": f"layers/{lid}.png", "default": default, **info})
            print(f"hamparan: {lid} ({info['size'][0]} x {info['size'][1]} px)")

    st = add_region(pd.read_parquet(path("interim") / "stations.parquet"))
    flat = st["flat_sensor"] if "flat_sensor" in st else False
    st = st[st["coord_ok"] & st["region_ok"] & ~flat].copy()
    mt_file = path("features") / "model_table.parquet"
    mt = pd.read_parquet(mt_file) if mt_file.exists() else pd.DataFrame(columns=["station_id", "date", "wl_cm"])
    if len(mt):
        st = st[st["station_id"].isin(mt["station_id"].unique())]
    pred_file = outputs / "predictions_latest.csv"
    pred = pd.read_csv(pred_file, parse_dates=["issue_date"]) if pred_file.exists() else pd.DataFrame()

    features, data_through = [], mt["date"].max() if len(mt) else None
    for s in st.itertuples():
        g = mt[mt["station_id"] == s.station_id].sort_values("date")
        tail = g.tail(args.series_days)
        last = g.iloc[-1] if len(g) else None
        preds = {}
        if len(pred):
            for r in pred[pred["station_id"] == s.station_id].itertuples():
                preds[f"h{int(r.horizon)}"] = {k: (None if pd.isna(v) else round(float(v), 3)) for k, v in
                                               {"delta_med": r.delta_med, "delta_q10": r.delta_q10, "delta_q90": r.delta_q90,
                                                "p_turun10": getattr(r, "p_turun10", np.nan),
                                                "p_turun10_basis": getattr(r, "p_turun10_basis", np.nan)}.items()}
        props = {"id": s.station_id, "name": getattr(s, "name", s.station_id), "region": s.region,
                 "last_date": None if last is None else str(last["date"].date()),
                 "wl_last_cm": None if last is None else round(float(last["wl_cm"]), 1),
                 "wl_d7_cm": None if last is None or pd.isna(last.get("wl_d7", np.nan)) else round(float(last["wl_d7"]), 1),
                 "pred": preds}
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(s.lon, 5), round(s.lat, 5)]}, "properties": props})
        series = {"id": s.station_id, "name": props["name"], "dates": [str(d.date()) for d in tail["date"]],
                  "wl_cm": [None if pd.isna(v) else round(float(v), 1) for v in tail["wl_cm"]], "pred": preds,
                  "issue_date": None if not len(pred) else str(pred["issue_date"].max().date())}
        (out / "series" / f"{s.station_id}.json").write_text(json.dumps(series, ensure_ascii=False), encoding="utf-8")
    (out / "stations.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False), encoding="utf-8")
    print(f"stasiun: {len(features)} | deret waktu: {len(features)} berkas")

    lons = [f["geometry"]["coordinates"][0] for f in features]
    lats = [f["geometry"]["coordinates"][1] for f in features]
    center = [float(np.mean(lats)), float(np.mean(lons))] if features else [-1.3, 104.0]
    kfile = out / "kerawanan.json"
    kerawanan = json.loads(kfile.read_text(encoding="utf-8")) if kfile.exists() else None
    hot = export_hotspots(out)
    fire = export_fire(out, outputs)
    dry = export_dryness(out, outputs)
    drivers = driver_status(len(features), mt, hot, dry)
    manifest = {"title": "Peringatan dini kekeringan gambut (prototipe)", "version": read_version(),
                "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "data_through": None if data_through is None else str(pd.Timestamp(data_through).date()),
                "issue_date": None if not len(pred) else str(pred["issue_date"].max().date()),
                "center": center, "validation": validation_block(outputs), "layers": layers,
                "stations": {"file": "stations.geojson", "n": len(features), "series_dir": "series/"},
                "basemap": (load_config().get("webmap") or {}).get("basemap"), "kerawanan": kerawanan, "hotspots": hot, "fire": fire, "dryness": dry, "drivers": drivers,
                "attribution": ATTRIBUTION, "disclaimer": DISCLAIMER}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print("manifest:", out / "manifest.json")
    print(f"validasi: {manifest['validation'].get('cap_label', 'belum ada')} | data sampai {manifest['data_through']} | terbit {manifest['issue_date']}")


if __name__ == "__main__":
    main()
