"""13_hotspots_to_cells: titik api mentah (L0) -> titik bersih (L1) -> tabel sel-hari 1 km.

    python scripts/13_hotspots_to_cells.py [--peat-gpkg data/raw/batas/gambut.gpkg --peat-layer NAMA] [--drop-persistent 300]

Masuk : data/raw/firms/**/*.csv.gz (12_fetch_firms.py)
Keluar: data/interim/hotspots.parquet        satu baris per deteksi: lon, lat, tanggal WIB, waktu UTC, FRP, keyakinan 0-2, siang/malam, sel 1 km
        data/features/fire_cell_day.parquet  per sel-hari: n, frp_sum, frp_max, n_high, n_day, n_night
        data/interim/fire_meta.json          pencatatan baris masuk dan keluar tiap tahap, rentang tanggal, jenis data (SP/NRT)

Aturan yang sengaja dijaga agar fitur latih dan fitur layan sama:
  - Bawaan hanya satelit Suomi NPP (SNPP; SP dan NRT). NOAA-20/21 menambah deteksi dan menggeser sebaran (--include-noaa bila tahu akibatnya).
  - Bila kolom `type` ada (data SP/arsip), hanya type 0 (diduga kebakaran vegetasi) dipertahankan; NRT tidak punya kolom itu, jadi sumber statis
    (flare migas, industri) lolos kecuali disaring oleh sebaran gambut atau --drop-persistent (lokasi dengan deteksi di >= N hari berbeda).
  - Duplikat (lat, lon, tanggal, jam, satelit) dibuang; bila ada di SP dan NRT sekaligus, SP yang dipakai.
  - Tanggal dihitung pada hari lokal WIB (UTC+7), sama dengan penjumlahan hujan GSMaP kita.
"""
import argparse
import gzip
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import path  # noqa: E402
from src.grid import lonlat_to_cell  # noqa: E402

CONF_MAP = {"l": 0, "low": 0, "n": 1, "nominal": 1, "h": 2, "high": 2, "0": 0, "1": 1, "2": 2}


def read_firms(root: Path) -> pd.DataFrame:
    frames = []
    for f in sorted(root.rglob("*.csv.gz")):
        rel = f.relative_to(root)
        top = rel.parts[0]
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            df = pd.read_csv(fh)
        if df.empty:
            continue
        df["source"] = top if top != "archive" else "archive:" + f.name.split("_")[0]
        df["product_type"] = "SP" if (top.endswith("_SP") or top == "archive") else "NRT"
        df["source_file"] = str(rel)
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--peat-gpkg"); p.add_argument("--peat-layer")
    p.add_argument("--keep-types", type=int, nargs="+", default=[0])
    p.add_argument("--include-noaa", action="store_true")
    p.add_argument("--drop-persistent", type=int, default=300, help="buang lokasi (dibulatkan 3 desimal) dengan deteksi di >= N hari berbeda; 0 = mati")
    p.add_argument("--bbox", type=float, nargs=4, metavar=("BARAT", "SELATAN", "TIMUR", "UTARA"))
    args = p.parse_args()

    root = path("raw") / "firms"
    raw = read_firms(root)
    if raw.empty:
        sys.exit(f"Tidak ada berkas titik api di {root}. Jalankan 12_fetch_firms.py dulu.")
    acc = [{"tahap": "baca mentah", "masuk": len(raw), "keluar": len(raw), "catatan": f"{raw['source_file'].nunique()} berkas"}]

    def stage(name: str, before: int, after: int, note: str = "") -> None:
        acc.append({"tahap": name, "masuk": before, "keluar": after, "catatan": note})

    need = {"latitude", "longitude", "acq_date", "acq_time"}
    missing = need - set(raw.columns)
    if missing:
        sys.exit(f"Kolom wajib hilang: {sorted(missing)}")
    n = len(raw)
    raw = raw.dropna(subset=list(need)).copy()
    stage("buang baris tanpa koordinat/tanggal/jam", n, len(raw))

    if not args.include_noaa:
        n = len(raw)
        raw = raw[raw["source"].str.contains("SNPP|snpp", regex=True)].copy()
        stage("hanya satelit Suomi NPP", n, len(raw), "gunakan --include-noaa untuk menambah NOAA-20/21")

    if "type" in raw.columns:
        n = len(raw)
        has_type = raw["type"].notna()
        raw = raw[~has_type | raw["type"].isin(args.keep_types)].copy()
        stage("saring jenis deteksi (type)", n, len(raw), f"dipertahankan type {args.keep_types}; baris tanpa type (NRT) dibiarkan")

    if args.bbox:
        n = len(raw)
        w, s, e, nn = args.bbox
        raw = raw[(raw.longitude.between(w, e)) & (raw.latitude.between(s, nn))].copy()
        stage("dalam bbox", n, len(raw))

    t = raw["acq_time"].astype(int).astype(str).str.zfill(4)
    raw["datetime_utc"] = pd.to_datetime(raw["acq_date"].astype(str) + " " + t.str[:2] + ":" + t.str[2:], utc=True, errors="coerce")
    n = len(raw)
    raw = raw.dropna(subset=["datetime_utc"]).copy()
    stage("buang waktu tak terbaca", n, len(raw))
    raw["date_wib"] = (raw["datetime_utc"] + pd.Timedelta(hours=7)).dt.tz_localize(None).dt.normalize()

    n = len(raw)
    raw["_prio"] = (raw["product_type"] != "SP").astype(int)   # SP lebih dulu agar dipertahankan
    raw = raw.sort_values(["_prio", "datetime_utc", "latitude", "longitude"], kind="mergesort")
    sat = raw["satellite"].astype(str) if "satellite" in raw.columns else pd.Series("", index=raw.index)
    raw = raw[~pd.DataFrame({"lat": raw.latitude.round(4), "lon": raw.longitude.round(4), "dt": raw.datetime_utc, "sat": sat}).duplicated()].copy()
    stage("buang duplikat (SP didahulukan atas NRT)", n, len(raw))

    if args.peat_gpkg:
        import geopandas as gpd
        n = len(raw)
        peat = gpd.read_file(args.peat_gpkg, layer=args.peat_layer) if args.peat_layer else gpd.read_file(args.peat_gpkg)
        peat = peat.set_crs(4326) if peat.crs is None else peat.to_crs(4326)
        pts = gpd.GeoDataFrame(raw, geometry=gpd.points_from_xy(raw.longitude, raw.latitude), crs=4326)
        keep = gpd.sjoin(pts[["geometry"]], peat[["geometry"]], how="inner", predicate="within").index.unique()
        raw = raw.loc[raw.index.isin(keep)].copy()
        stage("di dalam sebaran gambut", n, len(raw), Path(args.peat_gpkg).name)

    persistent_dropped = 0
    if args.drop_persistent:
        n = len(raw)
        loc = raw.latitude.round(3).astype(str) + "_" + raw.longitude.round(3).astype(str)
        days = raw.assign(_loc=loc).groupby("_loc")["date_wib"].nunique()
        bad = set(days[days >= args.drop_persistent].index)
        persistent_dropped = len(bad)
        raw = raw[~loc.isin(bad)].copy()
        stage("buang sumber persisten (diduga flare/industri)", n, len(raw), f"{persistent_dropped} lokasi dengan deteksi di >= {args.drop_persistent} hari")

    conf = raw["confidence"].astype(str).str.lower().map(CONF_MAP) if "confidence" in raw.columns else pd.Series(np.nan, index=raw.index)
    raw["conf_cls"] = conf.fillna(1).astype("int8")
    raw["frp"] = pd.to_numeric(raw.get("frp"), errors="coerce")
    raw["daynight"] = raw.get("daynight", pd.Series("", index=raw.index)).astype(str).str.upper().str[:1]
    cx, cy, cid = lonlat_to_cell(raw["longitude"].to_numpy(), raw["latitude"].to_numpy(), 1000)
    out = pd.DataFrame({"lon": raw["longitude"].to_numpy(), "lat": raw["latitude"].to_numpy(), "date": raw["date_wib"].to_numpy(),
                        "datetime_utc": raw["datetime_utc"].dt.tz_localize(None).to_numpy(), "frp": raw["frp"].to_numpy(),
                        "conf": raw["conf_cls"].to_numpy(), "daynight": raw["daynight"].to_numpy(), "source": raw["source"].to_numpy(),
                        "product_type": raw["product_type"].to_numpy(), "cx": cx, "cy": cy, "cell_id": cid})
    out = out.sort_values(["date", "cell_id", "datetime_utc"], kind="mergesort").reset_index(drop=True)   # urutan deterministik
    stage("hasil bersih (titik)", len(out), len(out))

    cells = out.groupby(["cell_id", "date"], sort=True).agg(
        n=("lon", "size"), frp_sum=("frp", "sum"), frp_max=("frp", "max"), n_high=("conf", lambda s: int((s == 2).sum())),
        n_day=("daynight", lambda s: int((s == "D").sum())), n_night=("daynight", lambda s: int((s == "N").sum()))).reset_index()
    stage("agregasi sel-hari 1 km", len(out), len(cells))

    path("interim").mkdir(parents=True, exist_ok=True); path("features").mkdir(parents=True, exist_ok=True)
    out.to_parquet(path("interim") / "hotspots.parquet", index=False)
    cells.to_parquet(path("features") / "fire_cell_day.parquet", index=False)
    meta = {"accounting": acc, "date_min": str(out["date"].min().date()), "date_max": str(out["date"].max().date()), "n_points": int(len(out)),
            "n_cell_days": int(len(cells)), "product_type_counts": out["product_type"].value_counts().to_dict(), "source_counts": out["source"].value_counts().to_dict(),
            "persistent_locations_dropped": persistent_dropped, "grid": "ESRI:54034, sel 1 km", "timezone": "tanggal WIB (UTC+7)"}
    (path("interim") / "fire_meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    for a in acc:
        print(f"{a['tahap']:48s} {a['masuk']:>9,} -> {a['keluar']:>9,}  {a['catatan']}")
    print(f"\nrentang {meta['date_min']} s/d {meta['date_max']} | jenis data {meta['product_type_counts']} | sel-hari {len(cells):,}")


if __name__ == "__main__":
    main()
