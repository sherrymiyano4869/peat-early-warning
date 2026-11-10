"""08_susceptibility: indeks kerawanan relatif per sel (seamless), disusun dari lapisan yang tersedia di mana-mana.

    python scripts/08_susceptibility.py [--peat-gpkg data/raw/batas/gambut.gpkg --peat-layer NAMA]

Masuk : data/features/grid/static.tif (07); opsional lulc.tif (band `lulc`, kode ESA WorldCover) dan dynamic.tif
        (band `dry_days`, `rain_deficit_mm`, `ndmi_dryness`), semuanya pada grid yang sama dengan static.tif
Keluar: data/features/grid/risk_index.tif (0-1), risk_class.tif (1-5, 0 = tanpa nilai), kerawanan_meta.json,
        data/features/grid/reference_quantiles.json (acuan tetap agar kelas stabil antar-run)

Ini INDEKS RELATIF, bukan peluang kebakaran. Tiap komponen diubah menjadi peringkat (0-1) terhadap distribusi acuan yang disimpan
pada run pertama, lalu dirata-ratakan berbobot. Arah dan bobot adalah ASUMSI yang dituliskan di bawah dan disimpan di
kerawanan_meta.json; uji kepekaannya sebelum dipakai untuk klaim. Tanpa dynamic.tif, indeks hanya kerentanan STRUKTURAL.
Sel air, terbangun, dan bakau (WorldCover 80, 50, 95) dikeluarkan bila lulc.tif ada. Bobot LULC bawaan 0 (belum dikalibrasi).
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import rasterize

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import path  # noqa: E402

# komponen struktural: nama band -> bobot (arah: nilai lebih besar = lebih rentan; ASUMSI hidrologis)
STATIC_WEIGHTS = {"canal_kde_500m": 0.35, "canal_kde_250m": 0.25, "fabdem_relief_1km": 0.25, "fabdem_relief_500m": 0.15}
DYNAMIC_WEIGHTS = {"dry_days": 0.40, "rain_deficit_mm": 0.30, "ndmi_dryness": 0.30}
STRUCT_VS_DYNAMIC = (0.5, 0.5)
EXCLUDE_LULC = (80, 50, 95)  # air, terbangun, bakau
N_CLASSES = 5


def read_bands(file: Path):
    with rasterio.open(file) as src:
        return {name: src.read(i + 1).astype("float64") for i, name in enumerate(src.descriptions)}, src.profile


def rank_normalize(values: np.ndarray, reference_q: np.ndarray) -> np.ndarray:
    """Nilai -> peringkat 0-1 terhadap kuantil acuan (101 titik, monoton); di luar rentang ditahan di 0 atau 1."""
    q = np.maximum.accumulate(np.asarray(reference_q, dtype=float))
    out = np.interp(values, q, np.linspace(0, 1, len(q)))
    out[~np.isfinite(values)] = np.nan
    return out


def weighted_mean(parts: dict, weights: dict) -> np.ndarray:
    num, den = 0.0, 0.0
    for name, arr in parts.items():
        valid = np.isfinite(arr)
        num = num + np.where(valid, arr * weights[name], 0.0)
        den = den + np.where(valid, weights[name], 0.0)
    return np.where(den > 0, num / np.where(den > 0, den, 1), np.nan)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--peat-gpkg", help="sebaran gambut (BlueBook); sel di luar gambut dikeluarkan")
    parser.add_argument("--peat-layer")
    parser.add_argument("--refresh-reference", action="store_true", help="hitung ulang distribusi acuan dan batas kelas")
    args = parser.parse_args()

    grid = path("features") / "grid"
    if not (grid / "static.tif").exists():
        sys.exit("static.tif tidak ada. Jalankan 07_grid_static.py dulu.")
    static, profile = read_bands(grid / "static.tif")
    shape = next(iter(static.values())).shape

    keep = np.ones(shape, bool)  # penutup: air/terbangun/bakau dan (opsional) di luar gambut
    lulc = None
    if (grid / "lulc.tif").exists():
        lulc = read_bands(grid / "lulc.tif")[0].get("lulc")
        if lulc is not None:
            keep &= ~np.isin(lulc, EXCLUDE_LULC)
    if args.peat_gpkg:
        import geopandas as gpd
        peat = gpd.read_file(args.peat_gpkg, layer=args.peat_layer) if args.peat_layer else gpd.read_file(args.peat_gpkg)
        peat = peat.set_crs(4326) if peat.crs is None else peat
        geoms = [(g, 1) for g in peat.to_crs(profile["crs"]).geometry if g is not None and not g.is_empty]
        keep &= rasterize(geoms, out_shape=shape, transform=profile["transform"], fill=0, dtype="uint8").astype(bool)

    ref_file = grid / "reference_quantiles.json"
    reference = json.loads(ref_file.read_text()) if ref_file.exists() and not args.refresh_reference else {"components": {}, "breaks": {}}
    changed = {"reference": False}

    def ranks(bands: dict, weights: dict) -> dict:
        out = {}
        for name in weights:
            if name not in bands:
                continue
            arr = np.where(keep, bands[name], np.nan)
            if name not in reference["components"]:
                valid = arr[np.isfinite(arr)]
                if valid.size == 0:
                    continue
                reference["components"][name] = np.percentile(valid, np.linspace(0, 100, 101)).tolist()
                changed["reference"] = True
            out[name] = rank_normalize(arr, reference["components"][name])
        return out

    s_parts = ranks(static, STATIC_WEIGHTS)
    if not s_parts:
        sys.exit("Tidak ada komponen struktural yang cocok di static.tif.")
    structural = weighted_mean(s_parts, STATIC_WEIGHTS)
    mode, used, index = "struktural", {"struktural": {k: STATIC_WEIGHTS[k] for k in s_parts}}, structural

    if (grid / "dynamic.tif").exists():
        d_parts = ranks(read_bands(grid / "dynamic.tif")[0], DYNAMIC_WEIGHTS)
        if d_parts:
            dynamic = weighted_mean(d_parts, DYNAMIC_WEIGHTS)
            ws, wd = STRUCT_VS_DYNAMIC
            index = np.where(np.isfinite(dynamic), ws * structural + wd * dynamic, np.nan)
            mode = "struktural+dinamis"
            used["dinamis"], used["gabungan"] = {k: DYNAMIC_WEIGHTS[k] for k in d_parts}, {"struktural": ws, "dinamis": wd}

    if mode not in reference["breaks"] or args.refresh_reference:  # batas kelas tetap antar-run setelah ditetapkan
        valid = index[np.isfinite(index)]
        reference["breaks"][mode] = np.percentile(valid, np.linspace(0, 100, N_CLASSES + 1)[1:-1]).tolist()
        changed["reference"] = True
    breaks = reference["breaks"][mode]
    klass = np.where(np.isfinite(index), np.digitize(index, breaks) + 1, 0).astype("uint8")
    if changed["reference"]:
        reference["created"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        ref_file.write_text(json.dumps(reference))

    base = profile | {"count": 1, "compress": "lzw"}
    with rasterio.open(grid / "risk_index.tif", "w", **(base | {"dtype": "float32", "nodata": np.nan})) as dst:
        dst.write(index.astype("float32"), 1)
        dst.set_band_description(1, "risk_index")
    with rasterio.open(grid / "risk_class.tif", "w", **(base | {"dtype": "uint8", "nodata": 0})) as dst:
        dst.write(klass, 1)
        dst.set_band_description(1, "risk_class")
    meta = {"mode": mode, "components": used, "class_breaks": breaks, "n_classes": N_CLASSES, "lulc_masked": lulc is not None,
            "peat_masked": bool(args.peat_gpkg),
            "note": "Indeks relatif, bukan peluang kebakaran. Arah dan bobot komponen adalah asumsi; uji kepekaan sebelum dipakai untuk klaim.",
            "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    (grid / "kerawanan_meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))

    print(f"mode: {mode} | komponen: {used}")
    print(f"sel bernilai: {int((klass > 0).sum()):,} dari {klass.size:,} | batas kelas: {[round(b, 3) for b in breaks]}")
    print("sebaran kelas 1-5:", [int((klass == k).sum()) for k in range(1, N_CLASSES + 1)])
    print("Tersimpan di", grid)


if __name__ == "__main__":
    main()
