"""02_gee_features: ekstraksi fitur Earth Engine di titik stasiun (GEE hanya untuk mengambil data).

    python scripts/02_gee_features.py --dry-run                      # lihat rencana, tanpa menyentuh GEE
    python scripts/02_gee_features.py --limit 3 --only static,gsmap  # uji kecil dulu
    python scripts/02_gee_features.py                                # static + gsmap
    python scripts/02_gee_features.py --only chirps                  # CHIRPS (pembanding; tertinggal di GEE)
    python scripts/02_gee_features.py --only s1,s2                   # Sentinel-1 dan NDMI (lebih berat)

Masuk : data/interim/stations.parquet (hasil 01_stations)
Keluar: data/features/gee_static.parquet, gee_chirps.parquet, gee_s1.parquet, gee_s2.parquet
Berkas yang sudah ada dilewati (pakai --force untuk mengulang), supaya kuota EECU tidak terbuang.
Dengan --limit N, hasil ditulis ke gee_<kelompok>_testN.parquet agar tidak tertukar dengan berkas penuh.

Kelompok:
  static : elevasi dan kemiringan (COPERNICUS/DEM/GLO30_2024_1; ini model permukaan, bukan tanah telanjang)
  chirps : hujan harian (UCSB-CHG/CHIRPS/DAILY) -> `rain_mm`; di GEE bisa tertinggal sekitar 5 minggu
  gsmap  : hujan harian dari jumlah per jam (JAXA/GPM_L3/GSMaP/v8/operational, near-real-time) -> `rain_mm`
           dijumlahkan pada HARI LOKAL (WIB, --rain-tz-offset 7) agar sejajar dengan muka air; resolusi 0,1 derajat;
           cantumkan atribusi JAXA GSMaP di slide
  chirps_long : CHIRPS harian bulan-bulan musim (default Jun-Nov) sejak --long-start (default 1981), untuk modul musiman
           (05_seasonal_outlook); satu permintaan per tahun
  s1     : median VV dan VH per jendela 12 hari (COPERNICUS/S1_GRD) di sekitar titik
  s2     : median NDMI per jendela 10 hari (COPERNICUS/S2_SR_HARMONIZED + Cloud Score+)
Sentinel dihitung per jendela dan per kelompok stasiun yang berdekatan (--batch-size), dengan filterBounds pada
titik (bukan kotak batas seluruh stasiun); kelompok yang gagal karena memori dibelah dua dan diulang.
"""
import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import load_config, path  # noqa: E402
from src.regions import add_region  # noqa: E402
from src.gee_utils import date_chunks, date_windows, parse_daily_bands, parse_window_bands  # noqa: E402

GROUPS = ("static", "chirps", "gsmap", "chirps_long", "s1", "s2")


def load_stations(limit):
    st = pd.read_parquet(path("interim") / "stations.parquet")
    st = add_region(st)
    flat = st["flat_sensor"] if "flat_sensor" in st else False
    st = st[st["coord_ok"] & st["region_ok"] & ~flat & ((st["n_30min"] > 0) | (st["n_daily"] > 0))].copy()
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


def reduce_at(ee, image, fc, reducer, scale, tile_scale=4):
    return image.reduceRegions(collection=fc, reducer=reducer, scale=scale, tileScale=tile_scale).getInfo()["features"]


def extract_static(ee, st, buffer_m):
    col = ee.ImageCollection("COPERNICUS/DEM/GLO30_2024_1").select("DEM")
    dem = col.mosaic().setDefaultProjection(col.first().projection())
    img = dem.rename("elev_m").addBands(ee.Terrain.slope(dem).rename("slope_deg"))
    feats = reduce_at(ee, img, points_fc(ee, st, buffer_m), ee.Reducer.mean(), 30)
    return pd.DataFrame([{"station_id": f["properties"]["station_id"],
                          "elev_m": f["properties"].get("elev_m"),
                          "slope_deg": f["properties"].get("slope_deg")} for f in feats])


def extract_chirps(ee, st, start, end, chunk_days, quiet=False):
    fc, frames = points_fc(ee, st, 0), []
    for s, e in date_chunks(start, end, chunk_days):
        ic = (ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")
              .filterDate(str(s), str(e + timedelta(days=1))).select("precipitation"))
        n = ic.size().getInfo()
        if n == 0:
            if not quiet:
                print(f"  chirps {s}..{e}: belum tersedia, dilewati")
            continue
        feats = reduce_at(ee, ic.toBands(), fc, ee.Reducer.first(), 5566)
        frames.append(parse_daily_bands(feats, "precipitation"))
        if not quiet:
            print(f"  chirps {s}..{e}: {n} citra")
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["station_id", "date", "precipitation"])
    return df.rename(columns={"precipitation": "rain_mm"})


def last_full_local_day(ee, ic, tz_offset):
    """Hari lokal penuh terakhir yang tersedia (hari terakhir mungkin parsial)."""
    last_ms = ic.aggregate_max("system:time_start").getInfo()
    last_local = pd.to_datetime(last_ms, unit="ms") + pd.Timedelta(hours=tz_offset)
    return (last_local + pd.Timedelta(hours=1) - pd.Timedelta(days=1)).normalize().date()


def extract_gsmap(ee, st, start, end, chunk_days, tz_offset=7):
    """Hujan harian pada hari lokal: jumlah citra per jam dari 00:00 lokal sampai 24:00 lokal."""
    ic_all = ee.ImageCollection("JAXA/GPM_L3/GSMaP/v8/operational").select("hourlyPrecipRate")
    end = min(end, last_full_local_day(ee, ic_all, tz_offset))
    print(f"  gsmap: hari lokal penuh terakhir yang tersedia {end} (UTC+{tz_offset})")
    fc, frames = points_fc(ee, st, 0), []
    fmt = "%Y-%m-%dT%H:%M:%S"
    for s, e in date_chunks(start, end, chunk_days):
        days = pd.date_range(s, e)
        imgs = []
        for d in days:
            t0 = d - pd.Timedelta(hours=tz_offset)  # awal hari lokal dinyatakan dalam UTC
            imgs.append(ic_all.filterDate(t0.strftime(fmt), (t0 + pd.Timedelta(days=1)).strftime(fmt)).sum().rename(f"{d:%Y%m%d}_rain"))
        feats = reduce_at(ee, ee.Image.cat(imgs), fc, ee.Reducer.first(), 11132)
        frames.append(parse_daily_bands(feats, "rain"))
        print(f"  gsmap {s}..{e}: {len(days)} hari")
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["station_id", "date", "rain"])
    return df.rename(columns={"rain": "rain_mm"})


def extract_chirps_long(ee, st, first_year, last_day, months):
    """CHIRPS harian pada bulan-bulan musim tiap tahun; satu permintaan per tahun."""
    frames = []
    for year in range(first_year, last_day.year + 1):
        s = date(year, months[0], 1)
        e = min((pd.Timestamp(year, months[1], 1) + pd.offsets.MonthEnd(0)).date(), last_day)
        if s > last_day:
            continue
        part = extract_chirps(ee, st, s, e, 400, quiet=True)
        if len(part):
            frames.append(part)
        print(f"  chirps_long {year}: {len(part)} baris")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["station_id", "date", "rain_mm"])


def station_batches(st: pd.DataFrame, size: int) -> list:
    """Kelompok stasiun yang berdekatan (diurutkan menurut bujur lalu lintang) agar tiap permintaan kecil."""
    ordered = st.sort_values(["lon", "lat"]).reset_index(drop=True)
    return [ordered.iloc[i:i + size] for i in range(0, len(ordered), size)]


def reduce_with_split(ee, image, batch, buffer_m, scale, tile_scale, names, key):
    """reduceRegions pada satu kelompok; bila gagal (mis. memori), belah dua dan ulangi."""
    try:
        feats = reduce_at(ee, image, points_fc(ee, batch, buffer_m), ee.Reducer.mean(), scale, tile_scale)
        return parse_window_bands(feats, names, fallback_key=key)
    except Exception as err:  # noqa: BLE001
        if len(batch) <= 1:
            print(f"    gagal untuk {batch['station_id'].iloc[0]}: {str(err)[:90]}")
            return pd.DataFrame(columns=["station_id", "window_start", *names])
        half = len(batch) // 2
        print(f"    kelompok {len(batch)} stasiun gagal ({str(err)[:60]}); dibelah menjadi {half} + {len(batch) - half}")
        parts = [reduce_with_split(ee, image, b, buffer_m, scale, tile_scale, names, key) for b in (batch.iloc[:half], batch.iloc[half:])]
        return pd.concat(parts, ignore_index=True)


def composite_windows(ee, st, start, end, step_days, buffer_m, build, names, batch_size, tile_scale):
    """Satu permintaan per (jendela, kelompok stasiun); `build` membuat citra komposit atau None."""
    frames, batches = [], station_batches(st, batch_size)
    for s_, e_ in date_windows(start, end, step_days):
        key, done = f"w{s_:%Y%m%d}", 0
        for batch in batches:
            fc = points_fc(ee, batch, buffer_m)
            image = build(ee, fc, s_, e_, key)
            if image is None:
                continue
            part = reduce_with_split(ee, image, batch, buffer_m, 20, tile_scale, names, key)
            if len(part):
                frames.append(part)
                done += 1
            else:
                print(f"    PERINGATAN: kelompok {len(batch)} stasiun menghasilkan 0 baris pada jendela {s_} (citra ada, tapi tidak ada nilai terbaca)")
        print(f"  jendela {s_}: {done}/{len(batches)} kelompok berhasil")
    if not frames:
        return pd.DataFrame(columns=["station_id", "window_start", *names, "window_end"])
    df = pd.concat(frames, ignore_index=True).drop_duplicates(["station_id", "window_start"])
    df["window_end"] = df["window_start"] + pd.Timedelta(days=step_days)
    return df


def build_s1(ee, fc, s_, e_, key):
    coll = (ee.ImageCollection("COPERNICUS/S1_GRD")
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
            .filterBounds(fc).filterDate(str(s_), str(e_)))
    if coll.size().getInfo() == 0:
        return None
    return coll.select(["VV", "VH"]).median().rename([f"{key}_vv", f"{key}_vh"])


def build_s2(ee, fc, s_, e_, key):
    coll = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(fc).filterDate(str(s_), str(e_))
    if coll.size().getInfo() == 0:
        return None
    cloud = ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED")
    masked = coll.linkCollection(cloud, ["cs_cdf"]).map(lambda im: im.updateMask(im.select("cs_cdf").gte(0.6)))
    ndmi = masked.map(lambda im: im.normalizedDifference(["B8", "B11"]).rename("ndmi")).median()
    return ndmi.rename(f"{key}_ndmi")


def extract_s1(ee, st, start, end, step_days, buffer_m, batch_size, tile_scale):
    return composite_windows(ee, st, start, end, step_days, buffer_m, build_s1, ["vv", "vh"], batch_size, tile_scale)


def extract_s2(ee, st, start, end, step_days, buffer_m, batch_size, tile_scale):
    return composite_windows(ee, st, start, end, step_days, buffer_m, build_s2, ["ndmi"], batch_size, tile_scale)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", default="static,gsmap", help=f"kelompok dipisah koma dari {GROUPS}")
    parser.add_argument("--limit", type=int, help="hanya N stasiun pertama (uji)")
    parser.add_argument("--pad-before", type=int, default=40, help="hari sebelum data pertama (untuk fitur hujan terdahulu)")
    parser.add_argument("--chunk-days", type=int, default=90)
    parser.add_argument("--buffer-m", type=int, default=100, help="radius penyangga untuk DEM, S1, dan S2")
    parser.add_argument("--batch-size", type=int, default=15, help="stasiun per permintaan Sentinel (kecil = hemat memori)")
    parser.add_argument("--tile-scale", type=float, default=16, help="tileScale reduceRegions untuk Sentinel (maks 16)")
    parser.add_argument("--rain-tz-offset", type=int, default=7, help="selisih jam lokal terhadap UTC untuk hari hujan GSMaP")
    parser.add_argument("--long-start", type=int, default=1981, help="tahun awal untuk chirps_long")
    parser.add_argument("--season-months", type=int, nargs=2, default=[6, 11], help="bulan awal dan akhir musim untuk chirps_long")
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
          f"S1 {len(date_windows(start, end, 12))} jendela, S2 {len(date_windows(start, end, 10))} jendela, "
          f"{len(station_batches(st, args.batch_size))} kelompok stasiun per jendela; "
          f"chirps_long {max(end.year - args.long_start + 1, 0)} tahun")
    if args.dry_run:
        print("(dry-run: tidak menyentuh Earth Engine)")
        return

    import ee  # noqa: PLC0415

    project = load_config()["gee"]["project"]
    if "GANTI" in project:
        sys.exit("Isi gee.project di config.yaml dulu.")
    ee.Initialize(project=project)

    for group in groups:
        suffix = f"_test{args.limit}" if args.limit else ""  # uji kecil tidak menimpa berkas penuh
        target = out_dir / f"gee_{group}{suffix}.parquet"
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
        elif group == "gsmap":
            df = extract_gsmap(ee, st, start, end, args.chunk_days, args.rain_tz_offset)
            if len(df):
                print(f"  data hujan terakhir: {df['date'].max().date()} (bandingkan dengan {end})")
        elif group == "chirps_long":
            df = extract_chirps_long(ee, st, args.long_start, end, args.season_months)
        elif group == "s1":
            df = extract_s1(ee, st, start, end, 12, args.buffer_m, args.batch_size, args.tile_scale)
        else:
            df = extract_s2(ee, st, start, end, 10, args.buffer_m, args.batch_size, args.tile_scale)
        if df.empty:
            print(f"[{group}] HASIL KOSONG: tidak ditulis (agar run berikutnya tidak melewatinya). Periksa pesan di atas.")
            continue
        df.to_parquet(target, index=False)
        print(f"[{group}] {len(df)} baris -> {target.name} ({time.time() - t0:.0f} detik)")
    print("\nPantau pemakaian EECU di Cloud Console setelah uji pertama sebelum menjalankan penuh.")


if __name__ == "__main__":
    main()
