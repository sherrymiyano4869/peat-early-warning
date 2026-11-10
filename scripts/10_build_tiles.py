"""10_build_tiles: tampilan kerawanan tiga tingkat untuk WebGIS statis (generalisasi per skala).

    python scripts/10_build_tiles.py [--units-gpkg data/raw/batas/khg.gpkg --units-layer khg --units-name nama_khg]
                                    [--admin-gpkg ... --admin-layer ...] [--canal-gpkg ... --canal-layer ...]

Masuk : data/features/grid/{risk_index,risk_class,confidence_static}.tif, grid_meta.json, kerawanan_meta.json
        (opsional) outputs/walkforward_summary.csv untuk batas kelas kepercayaan dari skill
Keluar: webmap/data/units.geojson           tingkat 1 (zoom jauh): satu poligon per KHG (atau blok 5 km bila tanpa KHG)
        webmap/data/tiles/coarse/{z}/{x}/{y}.png   tingkat 2 (zoom menengah): sel 500 m
        webmap/data/tiles/fine/{z}/{x}/{y}.png     tingkat 3 (zoom dekat): sel 100 m
        webmap/data/boundaries_khg.geojson, boundaries_admin.geojson, canals.geojson (bila masukannya diberikan)
        webmap/data/kerawanan.json                 deskripsi tampilan, dibaca 09_export_web.py dan peramban

Palet: urutan kuning ke merah tua 5 kelas (ColorBrewer YlOrRd). Kepercayaan: kelas rendah = lebih transparan dan diarsir; sedang = agak
transparan; tinggi = pekat. Kepercayaan yang dihitung di sini baru dari jarak ke stasiun dan AOA (masukan dan rentang prediksi belum ada).
"""
import argparse
import json
import math
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from PIL import Image
from rasterio.features import rasterize
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import ROOT, path  # noqa: E402
from src.confidence import CLASS_LABEL, cap_from_skill, combine_confidence  # noqa: E402

PALETTE = [(255, 255, 178), (254, 204, 92), (253, 141, 60), (240, 59, 32), (189, 0, 38)]  # YlOrRd, 5 kelas
LABELS = ["sangat rendah", "rendah", "sedang", "tinggi", "sangat tinggi"]
ALPHA = {2: 235, 1: 190, 0: 150}  # menurut kelas kepercayaan
HATCH_COLOR = (50, 50, 50, 170)
WORLD = 2 * 20037508.342789244
ORIGIN = -20037508.342789244


def tile_bounds(z: int, x: int, y: int):
    size = WORLD / 2 ** z
    minx, maxy = ORIGIN + x * size, -ORIGIN - y * size
    return minx, maxy - size, minx + size, maxy


def lonlat_to_tile(lon: float, lat: float, z: int):
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    lat_r = math.radians(max(min(lat, 85.0511), -85.0511))
    y = int((1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n)
    return min(max(x, 0), n - 1), min(max(y, 0), n - 1)


def block_reduce(arr: np.ndarray, f: int, func=np.nanmean) -> np.ndarray:
    h, w = arr.shape
    ph, pw = (-h) % f, (-w) % f
    padded = np.pad(arr.astype("float64"), ((0, ph), (0, pw)), constant_values=np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        return func(padded.reshape(padded.shape[0] // f, f, padded.shape[1] // f, f), axis=(1, 3))


def confidence_class(dist, n10, di, thr, cap):
    res = combine_confidence(np.nan_to_num(dist, nan=999.0), np.nan_to_num(n10, nan=0.0), di, thr, max_class=cap)
    return res["class"].astype("uint8")


def render_rgba(cls: np.ndarray, conf1: np.ndarray) -> np.ndarray:
    """cls: 0 = kosong, 1-5 = kelas; conf1: 0 = kosong, 1-3 = kepercayaan rendah/sedang/tinggi."""
    rgba = np.zeros(cls.shape + (4,), dtype=np.uint8)
    valid = cls > 0
    palette = np.array([(0, 0, 0)] + PALETTE, dtype=np.uint8)
    rgba[..., :3] = palette[np.clip(cls, 0, 5)]
    alpha = np.array([0, ALPHA[0], ALPHA[1], ALPHA[2]], dtype=np.uint8)[np.clip(conf1, 0, 3)]
    rgba[..., 3] = np.where(valid, alpha, 0)
    yy, xx = np.indices(cls.shape)
    hatch = valid & (conf1 == 1) & (((xx + yy) % 8) < 2)  # diarsir hanya pada kepercayaan rendah
    rgba[hatch] = HATCH_COLOR
    return rgba


def write_tiles(layers: dict, transform, crs, shape, bbox_ll, zooms, out_dir: Path) -> int:
    count = 0
    for z in zooms:
        x0, y0 = lonlat_to_tile(bbox_ll[0], bbox_ll[3], z)
        x1, y1 = lonlat_to_tile(bbox_ll[2], bbox_ll[1], z)
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                minx, miny, maxx, maxy = tile_bounds(z, x, y)
                dst_t = from_origin(minx, maxy, (maxx - minx) / 256, (maxy - miny) / 256)
                out = {}
                for name, arr in layers.items():
                    dst = np.zeros((256, 256), dtype="uint8")
                    reproject(arr, dst, src_transform=transform, src_crs=crs, dst_transform=dst_t, dst_crs="EPSG:3857",
                              resampling=Resampling.nearest)
                    out[name] = dst
                if not (out["cls"] > 0).any():
                    continue
                target = out_dir / str(z) / str(x)
                target.mkdir(parents=True, exist_ok=True)
                Image.fromarray(render_rgba(out["cls"], out["conf"]), "RGBA").save(target / f"{y}.png", optimize=True)
                count += 1
    return count


def zonal_units(polys, names, cls, idx, conf, transform, crs, res, breaks):
    """Statistik per unit pada grid halus; polys dalam CRS grid."""
    feats = []
    from shapely.geometry import mapping
    from pyproj import Transformer
    import shapely
    to_ll = Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform
    for geom, name in zip(polys, names):
        mask = rasterize([(geom, 1)], out_shape=cls.shape, transform=transform, fill=0, dtype="uint8").astype(bool)
        valid = mask & (cls > 0)
        n = int(valid.sum())
        if n == 0:
            continue
        mean_idx = float(np.nanmean(idx[valid]))
        klass = int(np.digitize(mean_idx, breaks) + 1)
        coverage = min(1.0, n / max(geom.area / res ** 2, 1.0))
        simple = shapely.transform(geom.simplify(50, preserve_topology=True), lambda xy: np.column_stack(to_ll(xy[:, 0], xy[:, 1])))
        feats.append({"type": "Feature", "geometry": json.loads(json.dumps(mapping(simple))),
                      "properties": {"nama": str(name), "kelas": klass, "label": LABELS[klass - 1], "indeks_rata2": round(mean_idx, 3),
                                     "bagian_tinggi": round(float((cls[valid] >= 4).mean()), 3), "n_sel": n, "cakupan": round(coverage, 2),
                                     "kepercayaan_rendah": round(float((conf[valid] == 1).mean()), 3)}})
    return feats


def export_lines(gpkg, layer, bbox_ll, out_file, tol_m, keep_geom=None):
    import geopandas as gpd
    from shapely.geometry import box
    gdf = gpd.read_file(gpkg, layer=layer) if layer else gpd.read_file(gpkg)
    gdf = gdf.set_crs(4326) if gdf.crs is None else gdf.to_crs(4326)
    gdf = gdf[gdf.intersects(box(*bbox_ll))].copy()
    gdf["geometry"] = gdf.geometry.simplify(tol_m / 111_320, preserve_topology=True)
    cols = [c for c in gdf.columns if c != "geometry"][:3]
    gdf[cols + ["geometry"]].to_file(out_file, driver="GeoJSON", COORDINATE_PRECISION=5)
    return len(gdf)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--units-gpkg"); p.add_argument("--units-layer"); p.add_argument("--units-name", default=None)
    p.add_argument("--admin-gpkg"); p.add_argument("--admin-layer")
    p.add_argument("--canal-gpkg"); p.add_argument("--canal-layer")
    p.add_argument("--coarse-m", type=float, default=500.0)
    p.add_argument("--coarse-zooms", type=int, nargs=2, default=[9, 12])
    p.add_argument("--fine-zooms", type=int, nargs=2, default=[13, 15])
    p.add_argument("--cap", default="auto", help="auto | 0 | 1 | 2: batas kelas kepercayaan (auto = dari walkforward_summary.csv)")
    p.add_argument("--out", default=str(ROOT / "webmap" / "data"))
    args = p.parse_args()

    grid, out = path("features") / "grid", Path(args.out)
    for need in ("risk_index.tif", "risk_class.tif", "confidence_static.tif", "grid_meta.json", "kerawanan_meta.json"):
        if not (grid / need).exists():
            sys.exit(f"{need} tidak ada. Jalankan 07_grid_static.py dan 08_susceptibility.py dulu.")
    meta, kmeta = json.loads((grid / "grid_meta.json").read_text()), json.loads((grid / "kerawanan_meta.json").read_text())
    with rasterio.open(grid / "risk_index.tif") as s:
        idx, transform, crs, bounds = s.read(1).astype("float64"), s.transform, s.crs, s.bounds
    with rasterio.open(grid / "risk_class.tif") as s:
        cls = s.read(1)
    with rasterio.open(grid / "confidence_static.tif") as s:
        conf_bands = {n: s.read(i + 1).astype("float64") for i, n in enumerate(s.descriptions)}
    res = float(meta["res_m"])

    # batas kelas kepercayaan
    note_cap = ""
    wf = path("outputs") / "walkforward_summary.csv"
    if args.cap == "auto":
        if wf.exists():
            skills = pd.read_csv(wf)["skill_vs_persistensi"].astype(float)
            cap = cap_from_skill(float(skills.min()))
            note_cap = f"batas dari skill walk-forward terburuk {skills.min():.2f}: {CLASS_LABEL[cap]}"
        else:
            cap, note_cap = 2, "validasi belum ada; kepercayaan hanya dari jarak ke stasiun dan AOA (tanpa batas skill)"
    else:
        cap, note_cap = int(args.cap), f"batas kelas ditetapkan manual: {CLASS_LABEL[int(args.cap)]}"
    conf = confidence_class(conf_bands["dist_station_km"], conf_bands["n_stations_10km"], conf_bands["aoa_di"], meta["aoa_threshold"], cap)
    conf1 = np.where(cls > 0, conf + 1, 0).astype("uint8")
    print("kepercayaan:", note_cap, "| sebaran (rendah, sedang, tinggi):", [int(((conf1 == k + 1)).sum()) for k in range(3)])

    # tingkat 3: halus
    west, south, east, north = rasterio.warp.transform_bounds(crs, "EPSG:4326", *bounds)
    bbox_ll = (west, south, east, north)
    n_fine = write_tiles({"cls": cls, "conf": conf1}, transform, crs, cls.shape, bbox_ll, range(args.fine_zooms[0], args.fine_zooms[1] + 1), out / "tiles" / "fine")

    # tingkat 2: kasar (agregasi blok)
    f = max(1, int(round(args.coarse_m / res)))
    breaks = kmeta["class_breaks"]
    idx_c = block_reduce(np.where(cls > 0, idx, np.nan), f)
    cls_c = np.where(np.isfinite(idx_c), np.digitize(idx_c, breaks) + 1, 0).astype("uint8")
    dist_c, n10_c, di_c = (block_reduce(conf_bands[k], f) for k in ("dist_station_km", "n_stations_10km", "aoa_di"))
    conf_c = np.where(cls_c > 0, confidence_class(dist_c, n10_c, di_c, meta["aoa_threshold"], cap) + 1, 0).astype("uint8")
    t_c = from_origin(transform.c, transform.f, res * f, res * f)
    n_coarse = write_tiles({"cls": cls_c, "conf": conf_c}, t_c, crs, cls_c.shape, bbox_ll, range(args.coarse_zooms[0], args.coarse_zooms[1] + 1), out / "tiles" / "coarse")

    # tingkat 1: unit (KHG atau blok 5 km)
    unit_type = "KHG"
    if args.units_gpkg:
        import geopandas as gpd
        gdf = gpd.read_file(args.units_gpkg, layer=args.units_layer) if args.units_layer else gpd.read_file(args.units_gpkg)
        gdf = (gdf.set_crs(4326) if gdf.crs is None else gdf).to_crs(crs)
        name_col = args.units_name or next((c for c in gdf.columns if c != "geometry"), None)
        polys, names = list(gdf.geometry), (list(gdf[name_col]) if name_col else [f"unit {i}" for i in range(len(gdf))])
    else:
        from shapely.geometry import box
        unit_type, size = "blok 5 km (sementara, tanpa batas KHG)", 5000.0
        polys, names = [], []
        for r in range(0, cls.shape[0], int(size / res)):
            for c in range(0, cls.shape[1], int(size / res)):
                x_min, y_max = transform.c + c * res, transform.f - r * res
                polys.append(box(x_min, y_max - size, x_min + size, y_max)); names.append(f"blok {r // int(size / res)}-{c // int(size / res)}")
    feats = zonal_units(polys, names, cls, idx, conf1, transform, crs, res, breaks)
    out.mkdir(parents=True, exist_ok=True)
    (out / "units.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False), encoding="utf-8")

    # batas dan kanal
    extra = {}
    pad = (west - 0.02, south - 0.02, east + 0.02, north + 0.02)
    if args.units_gpkg:
        extra["khg"] = export_lines(args.units_gpkg, args.units_layer, pad, out / "boundaries_khg.geojson", 50)
    if args.admin_gpkg:
        extra["admin"] = export_lines(args.admin_gpkg, args.admin_layer, pad, out / "boundaries_admin.geojson", 50)
    if args.canal_gpkg:
        extra["canals"] = export_lines(args.canal_gpkg, args.canal_layer, pad, out / "canals.geojson", 15)

    descriptor = {
        "title": "Kerawanan relatif", "mode": kmeta["mode"], "components": kmeta["components"], "unit_type": unit_type,
        "classes": [{"id": i + 1, "label": LABELS[i], "color": "#%02x%02x%02x" % PALETTE[i]} for i in range(5)],
        "levels": [
            {"id": "unit", "label": f"per {unit_type.split(' (')[0]}", "type": "geojson", "file": "units.geojson", "minZoom": 0, "maxZoom": args.coarse_zooms[0] + 1},
            {"id": "coarse", "label": f"sel {int(args.coarse_m)} m", "type": "tiles", "url": "tiles/coarse/{z}/{x}/{y}.png",
             "minZoom": args.coarse_zooms[0] + 2, "maxZoom": args.fine_zooms[0] - 1, "minNativeZoom": args.coarse_zooms[0], "maxNativeZoom": args.coarse_zooms[1]},
            {"id": "fine", "label": f"sel {int(res)} m", "type": "tiles", "url": "tiles/fine/{z}/{x}/{y}.png",
             "minZoom": args.fine_zooms[0], "maxZoom": 18, "minNativeZoom": args.fine_zooms[0], "maxNativeZoom": args.fine_zooms[1]}],
        "bounds": [[south, west], [north, east]],
        "confidence": {"cap": cap, "cap_label": CLASS_LABEL[cap], "note": note_cap,
                       "legend": [{"label": "tinggi", "style": "pekat"}, {"label": "sedang", "style": "agak transparan"}, {"label": "rendah", "style": "transparan dan diarsir"}]},
        "boundaries": {k: f"boundaries_{k}.geojson" if k != "canals" else "canals.geojson" for k in extra},
        "disclaimer": "Indeks relatif, bukan peluang kebakaran. Kelas dari ambang acuan tetap; kepercayaan ditunjukkan oleh transparansi dan arsiran.",
        "note": kmeta["note"]}
    (out / "kerawanan.json").write_text(json.dumps(descriptor, indent=1, ensure_ascii=False), encoding="utf-8")

    size_mb = sum(f.stat().st_size for f in (out / "tiles").rglob("*.png")) / 1e6 if (out / "tiles").exists() else 0
    print(f"tile halus {n_fine} | tile kasar {n_coarse} | total {size_mb:.1f} MB | unit {len(feats)} ({unit_type}) | batas {extra}")
    print("Tersimpan:", out / "kerawanan.json")


if __name__ == "__main__":
    main()
