"""Bantu untuk unduhan raster Earth Engine (getDownloadURL) yang dipetakan ke grid induk. Bagian ini murni lokal sehingga bisa diuji tanpa Earth Engine."""
import io
import zipfile

import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.warp import Resampling, reproject


def read_download(content: bytes, band_names: list):
    """Isi unduhan GEE -> daftar (array(band, tinggi, lebar), transform, crs, nama_band).
    Mendukung GeoTIFF tunggal berpita banyak (nama diambil dari urutan `band_names`) dan ZIP berisi satu TIFF per pita
    (nama pita diambil dari nama berkas, mis. 'xxx.frac_10.tif')."""
    out = []
    if content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for name in sorted(zf.namelist()):
                if not name.lower().endswith(".tif"):
                    continue
                with MemoryFile(zf.read(name)) as mf, mf.open() as src:
                    band = next((b for b in band_names if f".{b}." in name or name.endswith(f"{b}.tif")), None)
                    if band is None:
                        raise ValueError(f"Pita tak dikenali dari nama berkas ZIP: {name}")
                    out.append((src.read().astype("float32"), src.transform, src.crs, [band]))
    else:
        with MemoryFile(content) as mf, mf.open() as src:
            if src.count != len(band_names):
                raise ValueError(f"Jumlah pita unduhan {src.count} tidak sama dengan yang diminta ({len(band_names)})")
            out.append((src.read().astype("float32"), src.transform, src.crs, list(band_names)))
    return out


def to_master(band2d: np.ndarray, src_transform, src_crs, dst_transform, dst_shape, dst_crs, resampling=Resampling.average) -> np.ndarray:
    """Proyeksikan ulang satu pita ke grid induk; NaN di luar cakupan sumber."""
    dst = np.full(dst_shape, np.nan, dtype="float32")
    reproject(band2d, dst, src_transform=src_transform, src_crs=src_crs, src_nodata=np.nan, dst_transform=dst_transform, dst_crs=dst_crs,
              dst_nodata=np.nan, resampling=resampling)
    return dst


def merge_first(dst: np.ndarray, new: np.ndarray) -> np.ndarray:
    """Isi sel kosong (NaN) di dst dengan nilai dari new (ubin yang tumpang tindih tidak saling menimpa)."""
    return np.where(np.isfinite(dst), dst, new)


def tiles_for_bbox(bbox, tile_deg: float):
    """Pecah bbox (barat, selatan, timur, utara) menjadi ubin paling besar tile_deg derajat."""
    w, s, e, n = bbox
    xs = np.arange(w, e, tile_deg).tolist() + [e]
    ys = np.arange(s, n, tile_deg).tolist() + [n]
    return [(xs[i], ys[j], xs[i + 1], ys[j + 1]) for i in range(len(xs) - 1) for j in range(len(ys) - 1) if xs[i + 1] > xs[i] and ys[j + 1] > ys[j]]
