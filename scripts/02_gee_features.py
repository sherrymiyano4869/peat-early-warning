"""02_gee_features: ekstraksi fitur Earth Engine di titik stasiun (GEE hanya untuk mengambil data).

    python scripts/02_gee_features.py --dry-run                      # lihat rencana, tanpa menyentuh GEE
    python scripts/02_gee_features.py --limit 3 --only static,chirps # uji kecil dulu
    python scripts/02_gee_features.py                                # static + chirps
    python scripts/02_gee_features.py --only s1,s2                   # Sentinel-1 dan NDMI (lebih berat)

Masuk : data/interim/stations.parquet (hasil 01_stations)
Keluar: data/features/gee_static.parquet, gee_chirps.parquet, gee_s1.parquet, gee_s2.parquet
Berkas yang sudah ada dilewati (pakai --force untuk mengulang), supaya kuota EECU tidak terbuang.

Kelompok:
  static : elevasi dan kemiringan (COPERNICUS/DEM/GLO30; ini model permukaan, bukan tanah telanjang)
  chirps : hujan harian (UCSB-CHG/CHIRPS/DAILY) -> `rain_mm`
  s1     : median VV dan VH per jendela 12 hari (COPERNICUS/S1_GRD) di sekitar titik
  s2     : median NDMI per jendela 10 hari (COPERNICUS/S2_SR_HARMONIZED + Cloud Score+)
"""
import argparse
import sys
import time
from datetime import timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import load_config, path  # noqa: E402
from src.gee_utils import date_chunks, date_windows, parse_daily_bands, parse_window_bands  # noqa: E402

GROUPS = ("static", "chirps", "s1", "s2")


def load_stations(limit):
    st = pd.read_parquet(path("interim") / "stations.parquet")
    st = st[st["coord_ok"] & ((st["n_30min"] > 0) | (st["n_daily"] > 0))].copy()
    return (st.head(limit) if limit else st).reset_index(drop=True)


def date_span(st: pd.DataFrame, pad_before: int):
    firsts = pd.concat([st["first_ts"].dt.normalize(), st["daily_first"].dt.normalize()]).dropna()
    last = st["last_ts"].dt.normalize().max()
    return (firsts.min() - pd.Timedelta(days=pad_before)).date(), last.date()


# ---------- Earth Engine (diimpor hanya saat dibutuhkan) ----------

def points_fc(ee, st, buffer_m=0):
    feats = []
    for r in st.itertuples():
        geom = ee.Geometry.Point([float(r.lon), float(r.lat)])
        if buffer_m:
            geom = geom.buffer(buffer_m)
        feats.append(ee.Feature(geom, {"station_id": r.station_id}))
    return ee.FeatureCollection(feats)


def reduce_at(ee, image, fc, reducer, scale):
    return image.reduceRegions(collection=fc, reducer=reducer, scale=scale, tileScale=4).getInfo()["features"]


def extract_static(ee, st, buffer_m):
    col = ee.ImageCollection("COPERNICUS/DEM/GLO30").select("DEM")
    dem = col.mosaic().setDefaultProjection(col.first().projection())
    img = dem.rename("elev_m").addBands(ee.Terrain.slope(dem).rename("slope_deg"))
    feats = reduce_at(ee, img, points_fc(ee, st, buffer_m), ee.Reducer.mean(), 30)
    return pd.DataFrame([{"station_id": f["properties"]["station_id"],
                          "elev_m": f["properties"].get("elev_m"),
                          "slope_deg": f["properties"].get("slope_deg")} for f in feats])


def extract_chirps(ee, st, start, end, chunk_days):
    fc, frames = points_fc(ee, st, 0), []
    for s, e in date_chunks(start, end, chunk_days):
        ic = (ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")
              .filterDate(str(s), str(e + timedelta(days=1))).select("precipitation"))
        n = ic.size().getInfo()
        if n == 0:
            print(f"  chirps {s}..{e}: belum tersedia, dilewati")
            continue
        feats = reduce_at(ee, ic.toBands(), fc, ee.Reducer.first(), 5566)
        frames.append(parse_daily_bands(feats, "precipitation"))
        print(f"  chirps {s}..{e}: {n} citra")
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["station_id", "date", "precipitation"])
    return df.rename(columns={"precipitation": "rain_mm"})


def extract_s1(ee, st, start, end, step_days, buffer_m):
    fc, aoi = points_fc(ee, st, buffer_m), points_fc(ee, st, 0).geometry().bounds()
    base = (ee.ImageCollection("COPERNICUS/S1_GRD")
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
            .filterBounds(aoi))
    comps = []
    for s, e in date_windows(start, end, step_days):
        coll = base.filterDate(str(s), str(e))
        if coll.size().getInfo() == 0:
            continue
        key = f"w{s:%Y%m%d}"
        comps.append(coll.select(["VV", "VH"]).median().rename([f"{key}_vv", f"{key}_vh"]))
    if not comps:
        return pd.DataFrame(columns=["station_id", "window_start", "vv", "vh", "window_end"])
    df = parse_window_bands(reduce_at(ee, ee.Image.cat(comps), fc, ee.Reducer.mean(), 20), ["vv", "vh"])
    df["window_end"] = df["window_start"] + pd.Timedelta(days=step_days)
    return df


def extract_s2(ee, st, start, end, step_days, buffer_m):
    fc, aoi = points_fc(ee, st, buffer_m), points_fc(ee, st, 0).geometry().bounds()
    base = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(aoi)
    cloud = ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED")
    comps = []
    for s, e in date_windows(start, end, step_days):
        coll = base.filterDate(str(s), str(e))
        if coll.size().getInfo() == 0:
            continue
        masked = coll.linkCollection(cloud, ["cs_cdf"]).map(lambda im: im.updateMask(im.select("cs_cdf").gte(0.6)))
        ndmi = masked.map(lambda im: im.normalizedDifference(["B8", "B11"]).rename("ndmi")).median()
        comps.append(ndmi.rename(f"w{s:%Y%m%d}_ndmi"))
    if not comps:
        return pd.DataFrame(columns=["station_id", "window_start", "ndmi", "window_end"])
    df = parse_window_bands(reduce_at(ee, ee.Image.cat(comps), fc, ee.Reducer.mean(), 20), ["ndmi"])
    df["window_end"] = df["window_start"] + pd.Timedelta(days=step_days)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", default="static,chirps", help=f"kelompok dipisah koma dari {GROUPS}")
    parser.add_argument("--limit", type=int, help="hanya N stasiun pertama (uji)")
    parser.add_argument("--pad-before", type=int, default=40, help="hari sebelum data pertama (untuk fitur hujan terdahulu)")
    parser.add_argument("--chunk-days", type=int, default=90)
    parser.add_argument("--buffer-m", type=int, default=100, help="radius penyangga untuk DEM, S1, dan S2")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    groups = [g.strip() for g in args.only.split(",") if g.strip()]
    unknown = [g for g in groups if g not in GROUPS]
    if unknown:
        sys.exit(f"Kelompok tidak dikenal: {unknown}. Pilihan: {GROUPS}")

    st = load_stations(args.limit)
    start, end = date_span(st, args.pad_before)
    out_dir = path("features")
    print(f"stasiun: {len(st)} | rentang {start} .. {end} ({(end - start).days + 1} hari) | kelompok: {groups}")
    print(f"perkiraan: CHIRPS {len(date_chunks(start, end, args.chunk_days))} permintaan, "
          f"S1 {len(date_windows(start, end, 12))} jendela, S2 {len(date_windows(start, end, 10))} jendela")
    if args.dry_run:
        print("(dry-run: tidak menyentuh Earth Engine)")
        return

    import ee  # noqa: PLC0415

    project = load_config()["gee"]["project"]
    if "GANTI" in project:
        sys.exit("Isi gee.project di config.yaml dulu.")
    ee.Initialize(project=project)

    for group in groups:
        target = out_dir / f"gee_{group}.parquet"
        if target.exists() and not args.force:
            print(f"[{group}] sudah ada, dilewati ({target.name})")
            continue
        t0 = time.time()
        print(f"[{group}] mulai ...")
        if group == "static":
            df = extract_static(ee, st, args.buffer_m)
        elif group == "chirps":
            df = extract_chirps(ee, st, start, end, args.chunk_days)
            if len(df):
                print(f"  data hujan terakhir: {df['date'].max().date()} (bandingkan dengan {end})")
        elif group == "s1":
            df = extract_s1(ee, st, start, end, 12, args.buffer_m)
        else:
            df = extract_s2(ee, st, start, end, 10, args.buffer_m)
        df.to_parquet(target, index=False)
        print(f"[{group}] {len(df)} baris -> {target.name} ({time.time() - t0:.0f} detik)")
    print("\nPantau pemakaian EECU di Cloud Console setelah uji pertama sebelum menjalankan penuh.")


if __name__ == "__main__":
    main()
