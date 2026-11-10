"""07_grid_static: grid area pilot, fitur statis per sel, dan komponen kepercayaan yang tidak bergantung pada waktu.

    python scripts/07_grid_static.py [--bbox LON_MIN LAT_MIN LON_MAX LAT_MAX] [--res-m 100]

Masuk : data/raw/dem/fabdem_pilot.tif (02c), kanal gpkg (data/raw/kanal/kanal_osm_clip.gpkg), data/interim/stations.parquet
Keluar: data/features/grid/static.tif           fabdem_elev_m, fabdem_slope_deg, fabdem_relief_500m/1km, canal_kde_250m/500m
        data/features/grid/confidence_static.tif dist_station_km, n_stations_10km, aoa_di, inside_aoa
        data/features/grid/grid_meta.json
        data/features/grid_static_at_stations.parquet  nilai fitur yang sama di sel stasiun

Kerapatan kanal dihitung seperti peta panas (kernel density, kernel Gaussian): panjang kanal per sel diperhalus dengan Gaussian
berlebar sigma 250 m dan 500 m, satuan km kanal per km2. Sigma kecil menangkap kanal di sekitar titik, sigma besar menangkap
pola lanskap.

CRS: bawaan grid induk equal-area ESRI:54034 (src/grid.py), sel berjangkar di (0, 0) dan sejajar dengan sel 500 m dan 1 km; --crs utm untuk perilaku lama.

Prinsip konsistensi: fitur di stasiun diambil dari grid yang sama dengan fitur di sel peta (bukan dari 02c/02d), supaya model yang
dilatih di stasiun dan diterapkan ke sel memakai definisi fitur yang identik.

Kepercayaan (komponen statis):
  dist_station_km  : jarak ke stasiun acuan terdekat; makin jauh makin tidak terwakili
  n_stations_10km  : jumlah stasiun acuan dalam radius 10 km
  aoa_di           : indeks ketidakmiripan (jarak fitur ke stasiun terdekat dibagi rata-rata jarak antarstasiun), mengikuti gagasan
                     "area of applicability" (Meyer dan Pebesma, 2021; sitasi dari ingatan, verifikasi)
  inside_aoa       : 1 bila aoa_di di bawah ambang (persentil 75 + 1,5 x IQR dari DI stasiun terhadap stasiun lain), selain itu 0
Atribusi: FABDEM (c) DLR e.V. (CC BY-NC-SA 4.0); kanal (c) OpenStreetMap contributors (ODbL), BRGM BlueBook 2026.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import rasterio
import shapely
from pyproj import CRS, Transformer
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject
from scipy import ndimage
from scipy.signal import fftconvolve
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import path  # noqa: E402
from src.grid import bbox_to_grid, grid_crs  # noqa: E402
from src.regions import add_region  # noqa: E402

STATIC_BANDS = ["fabdem_elev_m", "fabdem_slope_deg", "fabdem_relief_500m", "fabdem_relief_1km", "canal_kde_250m", "canal_kde_500m"]
CONF_BANDS = ["dist_station_km", "n_stations_10km", "aoa_di", "inside_aoa"]


def utm_crs(lon: float, lat: float) -> CRS:
    zone = int((lon + 180) // 6) + 1
    return CRS.from_epsg((32600 if lat >= 0 else 32700) + zone)


def circle_kernel(radius_m: float, res: float) -> np.ndarray:
    n = int(math.ceil(radius_m / res))
    yy, xx = np.ogrid[-n:n + 1, -n:n + 1]
    return ((yy ** 2 + xx ** 2) * res ** 2 <= radius_m ** 2)


def canal_length_grid(lines: gpd.GeoDataFrame, x0: float, y_top: float, res: float, shape) -> np.ndarray:
    """Panjang kanal (km) per sel, dihitung dari potongan garis (tanpa pendekatan raster)."""
    lines = lines.explode(index_parts=False)
    seg = shapely.segmentize(lines.geometry.to_numpy(), max_segment_length=res / 10)
    coords, idx = shapely.get_coordinates(seg, return_index=True)
    same = idx[1:] == idx[:-1]
    p0, p1 = coords[:-1][same], coords[1:][same]
    length, mid = np.hypot(*(p1 - p0).T), (p0 + p1) / 2
    col, row = ((mid[:, 0] - x0) // res).astype(int), ((y_top - mid[:, 1]) // res).astype(int)
    ok = (row >= 0) & (row < shape[0]) & (col >= 0) & (col < shape[1])
    grid = np.zeros(shape)
    np.add.at(grid, (row[ok], col[ok]), length[ok])
    return grid / 1000.0


def kde_from_length(length_km: np.ndarray, sigma_m: float, res: float) -> np.ndarray:
    """Peta panas kanal: panjang kanal per sel diperhalus Gaussian (bobot kernel berjumlah 1), dibagi luas sel -> km/km2."""
    return ndimage.gaussian_filter(length_km, sigma=sigma_m / res, mode="constant", cval=0.0, truncate=4.0) / (res / 1000.0) ** 2


def dem_features(dem_path: Path, crs, transform, shape, res: float) -> dict:
    dem = np.full(shape, np.nan, dtype="float32")
    with rasterio.open(dem_path) as src:
        reproject(rasterio.band(src, 1), dem, src_transform=src.transform, src_crs=src.crs, src_nodata=src.nodata,
                  dst_transform=transform, dst_crs=crs, dst_nodata=np.nan, resampling=Resampling.average)
    dem[dem < -500] = np.nan
    dzdy, dzdx = np.gradient(dem, res)
    out = {"fabdem_elev_m": dem, "fabdem_slope_deg": np.degrees(np.arctan(np.hypot(dzdx, dzdy)))}
    for meters, name in ((500, "fabdem_relief_500m"), (1000, "fabdem_relief_1km")):
        filled = np.where(np.isnan(dem), np.inf, dem)
        low = ndimage.minimum_filter(filled, footprint=circle_kernel(meters, res), mode="constant", cval=np.inf)
        low[~np.isfinite(low)] = np.nan
        out[name] = dem - low
    return out


def aoa(cell_feats: np.ndarray, station_feats: np.ndarray):
    """Indeks ketidakmiripan terhadap stasiun acuan dan ambangnya (persentil 75 + 1,5 IQR dari DI stasiun-ke-stasiun lain)."""
    mu, sd = station_feats.mean(0), station_feats.std(0)
    sd[sd == 0] = 1.0
    S, Z = (station_feats - mu) / sd, (cell_feats - mu) / sd
    tree = cKDTree(S)
    pair = ((S[:, None, :] - S[None, :, :]) ** 2).sum(-1) ** 0.5
    dbar = pair[np.triu_indices(len(S), 1)].mean()
    di_train = tree.query(S, k=2)[0][:, 1] / dbar
    q1, q3 = np.percentile(di_train, [25, 75])
    thr = q3 + 1.5 * (q3 - q1)
    di = np.full(len(Z), np.nan)
    ok = np.isfinite(Z).all(1)
    di[ok] = tree.query(Z[ok])[0] / dbar
    return di, float(thr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bbox", type=float, nargs=4, metavar=("LON_MIN", "LAT_MIN", "LON_MAX", "LAT_MAX"))
    parser.add_argument("--res-m", type=float, default=100.0, help="harus membagi 1000 agar bersarang dengan sel 1 km")
    parser.add_argument("--crs", choices=["master", "utm"], default="master",
                        help="master = grid induk equal-area ESRI:54034 (bawaan); utm = zona UTM lokal (perilaku lama, tidak sejajar antar-pilot)")
    parser.add_argument("--dem", default=str(path("raw") / "dem" / "fabdem_pilot.tif"))
    parser.add_argument("--gpkg", default=str(path("raw") / "kanal" / "kanal_osm_clip.gpkg"))
    parser.add_argument("--layer", default="kanal_pilot_klaster5")
    args = parser.parse_args()

    dem_path, res = Path(args.dem), args.res_m
    if not dem_path.exists():
        sys.exit(f"DEM tidak ditemukan: {dem_path}. Jalankan 02c_fabdem_pilot.py dulu.")
    if args.bbox:
        lon_min, lat_min, lon_max, lat_max = args.bbox
    else:
        with rasterio.open(dem_path) as src:
            lon_min, lat_min, lon_max, lat_max = src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top
    if args.crs == "master":
        if 1000 % res:
            sys.exit("--res-m harus membagi 1000 (mis. 100, 250, 500) agar sejajar dengan grid induk.")
        crs = grid_crs()
        transform, shape, (x_min, y_min, x_max, y_max) = bbox_to_grid((lon_min, lat_min, lon_max, lat_max), res)
        x0, y_top = x_min, y_max
        height, width = shape
        to_utm = Transformer.from_crs("EPSG:4326", crs, always_xy=True)   # nama lama dipertahankan: transformer lon/lat -> CRS grid
    else:
        crs = utm_crs((lon_min + lon_max) / 2, (lat_min + lat_max) / 2)
        to_utm = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        xs, ys = to_utm.transform([lon_min, lon_max, lon_min, lon_max], [lat_min, lat_min, lat_max, lat_max])
        x0, y_top = math.floor(min(xs) / res) * res, math.ceil(max(ys) / res) * res
        width, height = int(math.ceil((max(xs) - x0) / res)), int(math.ceil((y_top - min(ys)) / res))
        transform, shape = from_origin(x0, y_top, res, res), (height, width)
    print(f"grid: {width} x {height} sel @ {res:.0f} m | CRS {crs.to_string()} ({'grid induk' if args.crs == 'master' else 'UTM lokal'}) | {width * height:,} sel")

    layers = [r[0] for r in pyogrio.list_layers(args.gpkg)] if Path(args.gpkg).exists() else []
    layer = args.layer if args.layer in layers else (layers[0] if layers else None)
    feats = dem_features(dem_path, crs, transform, shape, res)
    if layer is None:
        print("PERINGATAN: gpkg kanal tidak ditemukan; kerapatan kanal diisi NaN")
        feats["canal_kde_250m"] = feats["canal_kde_500m"] = np.full(shape, np.nan)
    else:
        canals = gpd.read_file(args.gpkg, layer=layer)
        canals = (canals.set_crs(4326) if canals.crs is None else canals.to_crs(4326)).to_crs(crs)
        canals = canals[canals.geometry.geom_type.isin(["LineString", "MultiLineString"])]
        length_km = canal_length_grid(canals, x0, y_top, res, shape)
        print(f"kanal: layer {layer}, {len(canals)} ruas, total {length_km.sum():,.0f} km di dalam grid")
        feats["canal_kde_250m"] = kde_from_length(length_km, 250, res)
        feats["canal_kde_500m"] = kde_from_length(length_km, 500, res)
    stack = np.stack([feats[b] for b in STATIC_BANDS]).astype("float32")

    # stasiun acuan: lolos QC dan berada di dalam grid
    st = add_region(pd.read_parquet(path("interim") / "stations.parquet"))
    flat = st["flat_sensor"] if "flat_sensor" in st else False
    st = st[st["coord_ok"] & st["region_ok"] & ~flat & ((st["n_30min"] > 0) | (st["n_daily"] > 0))].copy()
    sx, sy = to_utm.transform(st["lon"].to_numpy(), st["lat"].to_numpy())
    st["row"], st["col"] = ((y_top - np.asarray(sy)) // res).astype(int), ((np.asarray(sx) - x0) // res).astype(int)
    st = st[(st.row >= 0) & (st.row < height) & (st.col >= 0) & (st.col < width)].reset_index(drop=True)
    print(f"stasiun acuan di dalam grid: {len(st)}")
    if len(st) < 4:
        sys.exit("Stasiun acuan di dalam grid kurang dari 4; perluas --bbox atau cek stations.parquet.")
    at_st = pd.DataFrame({"station_id": st["station_id"], **{b: stack[i][st.row, st.col] for i, b in enumerate(STATIC_BANDS)}})

    mask = np.zeros(shape, bool)
    mask[st.row, st.col] = True
    dist_km = ndimage.distance_transform_edt(~mask) * res / 1000.0
    n10 = np.clip(np.rint(fftconvolve(mask.astype(float), circle_kernel(10_000, res).astype(float), mode="same")), 0, None)
    cell_feats = stack.reshape(len(STATIC_BANDS), -1).T
    usable = np.isfinite(at_st[STATIC_BANDS].to_numpy()).all(1)
    di, thr = aoa(cell_feats, at_st.loc[usable, STATIC_BANDS].to_numpy(float))
    di = di.reshape(shape)
    conf = np.stack([dist_km, n10, di, (di < thr).astype(float)]).astype("float32")
    conf[3][np.isnan(di)] = 0

    out_dir = path("features") / "grid"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, arr, bands in (("static.tif", stack, STATIC_BANDS), ("confidence_static.tif", conf, CONF_BANDS)):
        with rasterio.open(out_dir / name, "w", driver="GTiff", height=height, width=width, count=len(bands), dtype="float32",
                           crs=crs, transform=transform, nodata=np.nan, compress="lzw") as dst:
            dst.write(arr)
            for i, b in enumerate(bands, 1):
                dst.set_band_description(i, b)
    (out_dir / "grid_meta.json").write_text(json.dumps({"crs": crs.to_string(), "grid": args.crs, "res_m": res, "x0": x0, "y_top": y_top,
                                                       "width": width, "height": height, "aoa_threshold": thr}, indent=1))
    at_st.to_parquet(path("features") / "grid_static_at_stations.parquet", index=False)

    valid = np.isfinite(stack).all(0)
    print(f"\nsel dengan semua fitur statis: {valid.mean():.0%}")
    print("jarak ke stasiun terdekat: " + " | ".join(f"<= {k} km: {(dist_km <= k).mean():.0%}" for k in (2, 5, 10, 20)))
    print(f"di dalam area penerapan (AOA, ambang DI {thr:.2f}): {conf[3].mean():.0%} sel")
    print("Tersimpan di", out_dir, "dan data/features/grid_static_at_stations.parquet")


if __name__ == "__main__":
    main()
