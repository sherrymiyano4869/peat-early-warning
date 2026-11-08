"""00_setup: buat folder, inisialisasi Earth Engine, dan uji koneksi.

Jalankan sekali setelah `earthengine authenticate --quiet` di terminal WSL:
    python scripts/00_setup.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ee
from src.common import load_config, path


def init_ee(project: str) -> None:
    try:
        ee.Initialize(project=project)
    except Exception as err:
        sys.exit(
            "Gagal inisialisasi Earth Engine.\n"
            "1) Jalankan di terminal: earthengine authenticate --quiet\n"
            "2) Pastikan 'gee.project' di config.yaml berisi ID project Cloud "
            "yang sudah terdaftar nonkomersial.\n"
            f"Detail: {err}"
        )


def smoke_test(cfg: dict) -> None:
    lon, lat = cfg["pilot"]["test_point"]
    point = ee.Geometry.Point([lon, lat])
    chirps = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").filterDate("2025-01-01", "2025-01-11")
    n_images = chirps.size().getInfo()
    total = chirps.select("precipitation").sum().reduceRegion(
        reducer=ee.Reducer.first(), geometry=point, scale=5566
    ).getInfo()
    print(f"CHIRPS: {n_images} citra, hujan 10 hari di titik uji = {total}")


def main() -> None:
    cfg = load_config()
    for key in cfg["paths"]:
        print("folder:", path(key))
    init_ee(cfg["gee"]["project"])
    smoke_test(cfg)
    print("OK. Lanjut ke 01_stations.py setelah audit data SiTMAT selesai.")


if __name__ == "__main__":
    main()
