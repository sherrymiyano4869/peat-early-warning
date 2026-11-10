"""Grid induk: satu CRS equal-area dan satu sistem sel bersarang (100 m, 500 m, 1 km) untuk seluruh gambut Sumatra dan Kalimantan.

CRS: ESRI:54034 (World Cylindrical Equal Area, paralel standar 0 derajat). Dipilih untuk wilayah ekuator:
  - sama luas (sel "1 km" = 1 km2 di mana pun), dan
  - hampir tanpa distorsi bentuk: skala sepanjang paralel dan meridian berbeda paling banyak 0,55 persen pada 6 derajat dari ekuator.
EPSG:6933 (paralel standar 30 derajat) sama luas juga, tetapi di ekuator sel "1 km" menjadi 1,15 km x 0,87 km di tanah, sehingga jarak, kernel,
dan lingkungan 3x3 tersimpang sekitar 15 persen. Jarak dan kernel di sini dihitung langsung di CRS grid; di luar +-11 derajat lintang periksa lagi.

Sistem sel berjangkar di titik asal (0, 0) CRS, jadi sel 100 m, 500 m, dan 1 km sejajar dan agregasi 10x10 atau 2x2 akurat, dan grid dari pilot
yang berbeda otomatis sejajar. Berkas GeoTIFF/Parquet tidak bergantung pada kode EPSG khusus: CRS ditulis penuh.
"""
import math
from functools import lru_cache

import numpy as np
from pyproj import CRS, Transformer
from rasterio.transform import from_origin

GRID_CRS_CODE = "ESRI:54034"
RESOLUTIONS_M = (100, 500, 1000)
CELL_RES_M = 1000          # sel prediksi titik api
_OFFSET = 100_000          # menggeser indeks sel agar tak negatif untuk id bilangan bulat


def grid_crs() -> CRS:
    return CRS.from_user_input(GRID_CRS_CODE)


@lru_cache(maxsize=None)
def _fwd() -> Transformer:
    return Transformer.from_crs("EPSG:4326", grid_crs(), always_xy=True)


@lru_cache(maxsize=None)
def _inv() -> Transformer:
    return Transformer.from_crs(grid_crs(), "EPSG:4326", always_xy=True)


def to_grid(lon, lat):
    """lon/lat (derajat) -> x/y (meter) di CRS grid."""
    return _fwd().transform(lon, lat)


def from_grid(x, y):
    return _inv().transform(x, y)


def align_bounds(bounds, multiple_m: float = CELL_RES_M):
    """(xmin, ymin, xmax, ymax) -> diperluas keluar ke kelipatan `multiple_m` agar semua resolusi bersarang sejajar."""
    x0, y0, x1, y1 = bounds
    return (math.floor(x0 / multiple_m) * multiple_m, math.floor(y0 / multiple_m) * multiple_m,
            math.ceil(x1 / multiple_m) * multiple_m, math.ceil(y1 / multiple_m) * multiple_m)


def bbox_to_grid(bbox_lonlat, res_m: float):
    """bbox lon/lat -> (transform, (tinggi, lebar), (xmin, ymin, xmax, ymax)) pada grid induk beresolusi `res_m`."""
    lon_min, lat_min, lon_max, lat_max = bbox_lonlat
    xs, ys = to_grid([lon_min, lon_max, lon_min, lon_max], [lat_min, lat_min, lat_max, lat_max])
    xmin, ymin, xmax, ymax = align_bounds((min(xs), min(ys), max(xs), max(ys)), CELL_RES_M)
    shape = (int(round((ymax - ymin) / res_m)), int(round((xmax - xmin) / res_m)))
    return from_origin(xmin, ymax, res_m, res_m), shape, (xmin, ymin, xmax, ymax)


def lonlat_to_cell(lon, lat, res_m: float = CELL_RES_M):
    """lon/lat -> indeks sel global (cx, cy) dan id bilangan bulat unik; cy bertambah ke utara."""
    x, y = to_grid(np.asarray(lon, dtype=float), np.asarray(lat, dtype=float))
    cx, cy = np.floor(np.asarray(x) / res_m).astype("int64"), np.floor(np.asarray(y) / res_m).astype("int64")
    return cx, cy, cell_id(cx, cy)


def cell_id(cx, cy):
    return (np.asarray(cy, dtype="int64") + _OFFSET) * (2 * _OFFSET) + (np.asarray(cx, dtype="int64") + _OFFSET)


def cell_from_id(cid):
    cid = np.asarray(cid, dtype="int64")
    return cid % (2 * _OFFSET) - _OFFSET, cid // (2 * _OFFSET) - _OFFSET


def cell_center_lonlat(cx, cy, res_m: float = CELL_RES_M):
    return from_grid((np.asarray(cx) + 0.5) * res_m, (np.asarray(cy) + 0.5) * res_m)


def cell_polygon_lonlat(cx: int, cy: int, res_m: float = CELL_RES_M):
    """Poligon sel dalam lon/lat (cincin tertutup) untuk GeoJSON."""
    xs = [cx * res_m, (cx + 1) * res_m, (cx + 1) * res_m, cx * res_m, cx * res_m]
    ys = [cy * res_m, cy * res_m, (cy + 1) * res_m, (cy + 1) * res_m, cy * res_m]
    lon, lat = from_grid(xs, ys)
    return [[round(float(a), 5), round(float(b), 5)] for a, b in zip(lon, lat)]
