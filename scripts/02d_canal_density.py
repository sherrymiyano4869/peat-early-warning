"""02d_canal_density: kerapatan kanal (km kanal per km2) di sekitar tiap stasiun, dari gpkg kanal OSM yang sudah dipotong.

    python scripts/02d_canal_density.py
    python scripts/02d_canal_density.py --gpkg data/raw/kanal/kanal_osm_clip.gpkg --layer kanal_stasiun_10km

Keluaran: data/features/canal_density.parquet (canal_density_500m, canal_density_1km).
Jarak dihitung pada proyeksi azimutal lokal per stasiun (akurat untuk Sumatra dan Kalimantan sekaligus).
Sengaja hanya kerapatan, tanpa jenis kanal. Atribusi wajib: (c) OpenStreetMap contributors (ODbL); BRGM BlueBook 2026 sebagai pengompilasi.
"""
import argparse
import math
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import shapely
from pyproj import CRS, Transformer
from shapely.geometry import Point, box

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import path  # noqa: E402
from src.regions import add_region  # noqa: E402

RADII_M = (500, 1000)


def local_aeqd(lon: float, lat: float) -> CRS:
    return CRS.from_proj4(f"+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m +no_defs")


def density_at(lines: gpd.GeoDataFrame, lon: float, lat: float, radii=RADII_M) -> dict:
    """Panjang kanal dalam lingkaran (km) dibagi luas lingkaran (km2), untuk tiap radius."""
    pad = max(radii) / 111_320 * 1.5 + 0.002
    idx = lines.sindex.query(box(lon - pad, lat - pad, lon + pad, lat + pad), predicate="intersects")
    if len(idx) == 0:
        return {r: 0.0 for r in radii}
    to_local = Transformer.from_crs("EPSG:4326", local_aeqd(lon, lat), always_xy=True)
    geoms = [shapely.transform(g, lambda xy: np.column_stack(to_local.transform(xy[:, 0], xy[:, 1])))
             for g in lines.geometry.iloc[idx]]
    out = {}
    for r in radii:
        circle = Point(0, 0).buffer(r, 128)
        length_km = sum(g.intersection(circle).length for g in geoms) / 1000
        out[r] = length_km / (circle.area / 1e6)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gpkg", default=str(path("raw") / "kanal" / "kanal_osm_clip.gpkg"))
    parser.add_argument("--layer", default="kanal_stasiun_10km")
    args = parser.parse_args()

    if not Path(args.gpkg).exists():
        sys.exit(f"Berkas tidak ditemukan: {args.gpkg}")
    layers = [row[0] for row in pyogrio.list_layers(args.gpkg)]
    if args.layer not in layers:
        sys.exit(f"Layer '{args.layer}' tidak ada. Layer tersedia: {layers}")
    canals = gpd.read_file(args.gpkg, layer=args.layer)
    canals = canals.set_crs(4326) if canals.crs is None else canals.to_crs(4326)
    canals = canals[canals.geometry.geom_type.isin(["LineString", "MultiLineString"])].reset_index(drop=True)
    print(f"kanal: {len(canals)} ruas dari layer {args.layer}")

    st = add_region(pd.read_parquet(path("interim") / "stations.parquet"))
    st = st[st["coord_ok"] & st["region_ok"]]
    rows = []
    for s in st.itertuples():
        d = density_at(canals, s.lon, s.lat)
        rows.append({"station_id": s.station_id, "canal_density_500m": d[500], "canal_density_1km": d[1000]})
    out = pd.DataFrame(rows)
    out.to_parquet(path("features") / "canal_density.parquet", index=False)

    print(f"stasiun: {len(out)} | tanpa kanal dalam 1 km: {int((out.canal_density_1km == 0).sum())}")
    print("kerapatan (km/km2): median 500 m {:.2f} | median 1 km {:.2f} | maks 1 km {:.2f}".format(
        out.canal_density_500m.median(), out.canal_density_1km.median(), out.canal_density_1km.max()))
    print("Tersimpan: data/features/canal_density.parquet")
    print("Atribusi: (c) OpenStreetMap contributors (ODbL); BRGM BlueBook 2026.")


if __name__ == "__main__":
    main()
