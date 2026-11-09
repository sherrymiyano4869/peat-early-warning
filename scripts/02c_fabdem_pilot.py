"""02c_fabdem_pilot: ambil FABDEM hanya untuk area pilot dari portal data.bris, lalu hitung fitur medan di stasiun.

    python scripts/02c_fabdem_pilot.py --bbox 103.68 -1.61 104.17 -1.12 --check   # cek rencana, dukungan Range, dan isi arsip
    python scripts/02c_fabdem_pilot.py --bbox 103.68 -1.61 104.17 -1.12 --contact emailmu@contoh.com

FABDEM V1-2 (University of Bristol) tersedia sebagai arsip zip 10x10 derajat berisi ubin 1x1 derajat. Skrip ini membaca arsip
lewat HTTP Range (hanya daftar isi dan ubin yang dibutuhkan), bukan mengunduh seluruh arsip. Bila server tidak mendukung Range,
skrip berhenti dengan pesan; unduh arsip secara manual (cek ukurannya dulu) atau pakai grup `fabdem` di 02_gee_features.

Keluaran: data/raw/dem/fabdem_tiles/*.tif, data/raw/dem/fabdem_pilot.tif (klip bbox),
          data/features/dem_fabdem.parquet (fabdem_elev_m, fabdem_slope_deg, fabdem_relief_500m, fabdem_relief_1km)

Lisensi FABDEM: CC BY-NC-SA 4.0 (nonkomersial, ShareAlike). Wajib mencantumkan: "FABDEM is produced using Copernicus
WorldDEM-30 (c) DLR e.V." dan sitasi Hawker dkk. 2022. Turunan yang dibagikan ikut berlisensi sama.
Catatan akurasi: kesalahan vertikal FABDEM di hutan tropis beberapa meter, sedangkan relief kubah gambut hanya beberapa meter.
"""
import argparse
import io
import math
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import requests
from rasterio.merge import merge

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import path  # noqa: E402
from src.regions import add_region  # noqa: E402

BASE_URL = "https://data.bris.ac.uk/datasets/s5hqmjcdj8yo2ibzi9b4ew3sn/"
METERS_PER_DEGREE = 111_320.0


def tile_id(lat_floor: int, lon_floor: int) -> str:
    return f"{'N' if lat_floor >= 0 else 'S'}{abs(lat_floor):02d}{'E' if lon_floor >= 0 else 'W'}{abs(lon_floor):03d}"


def block_name(lat_floor: int, lon_floor: int) -> str:
    lat_lo, lon_lo = (lat_floor // 10) * 10, (lon_floor // 10) * 10
    lat_hi, lon_hi = lat_lo + 10, lon_lo + 10
    if lon_hi == 180:  # blok terakhir melewati bujur 180
        lon_hi_txt = "W180"
    else:
        lon_hi_txt = f"{'E' if lon_hi >= 0 else 'W'}{abs(lon_hi):03d}"
    return (f"{'N' if lat_lo >= 0 else 'S'}{abs(lat_lo):02d}{'E' if lon_lo >= 0 else 'W'}{abs(lon_lo):03d}-"
            f"{'N' if lat_hi >= 0 else 'S'}{abs(lat_hi):02d}{lon_hi_txt}")


def plan_tiles(bbox):
    lon_min, lat_min, lon_max, lat_max = bbox
    tiles = {}
    for lat in range(math.floor(lat_min), math.floor(lat_max) + 1):
        for lon in range(math.floor(lon_min), math.floor(lon_max) + 1):
            tiles.setdefault(block_name(lat, lon), []).append(tile_id(lat, lon))
    return tiles


class HTTPRangeFile(io.RawIOBase):
    """Berkas baca-saja di atas HTTP Range, agar zipfile bisa membaca sebagian arsip besar."""

    def __init__(self, url, session, timeout=120):
        self.url, self.session, self.timeout, self.pos = url, session, timeout, 0
        resp = session.get(url, headers={"Range": "bytes=0-0"}, timeout=timeout, stream=True)
        status, content_range = resp.status_code, resp.headers.get("Content-Range", "")
        resp.close()
        if status != 206 or "/" not in content_range:
            raise RuntimeError(f"Server tidak mendukung HTTP Range (status {status}) untuk {url}")
        self.size = int(content_range.split("/")[1])

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=io.SEEK_SET):
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self.pos, io.SEEK_END: self.size}[whence]
        self.pos = base + offset
        return self.pos

    def readinto(self, buf):
        if self.pos >= self.size:
            return 0
        end = min(self.pos + len(buf), self.size) - 1
        resp = self.session.get(self.url, headers={"Range": f"bytes={self.pos}-{end}"}, timeout=self.timeout)
        if resp.status_code != 206:
            raise RuntimeError(f"Permintaan Range gagal (status {resp.status_code})")
        data = resp.content
        buf[:len(data)] = data
        self.pos += len(data)
        return len(data)


def open_remote_zip(url, session):
    raw = HTTPRangeFile(url, session)
    return zipfile.ZipFile(io.BufferedReader(raw, buffer_size=4 << 20)), raw.size


def find_member(zf, tid):
    for name in zf.namelist():
        if tid in name and name.lower().endswith(".tif"):
            return name
    return None


def window_stats(arr, r, c, radius_px):
    """Minimum pada jendela melingkar; NaN bila jendela keluar dari raster."""
    if r - radius_px < 0 or c - radius_px < 0 or r + radius_px >= arr.shape[0] or c + radius_px >= arr.shape[1]:
        return np.nan
    win = arr[r - radius_px:r + radius_px + 1, c - radius_px:c + radius_px + 1]
    yy, xx = np.ogrid[-radius_px:radius_px + 1, -radius_px:radius_px + 1]
    return float(np.nanmin(np.where(yy ** 2 + xx ** 2 <= radius_px ** 2, win, np.nan)))


def station_features(stations: pd.DataFrame, tif: Path) -> pd.DataFrame:
    rows = []
    with rasterio.open(tif) as src:
        arr = src.read(1).astype(float)
        if src.nodata is not None:
            arr[arr == src.nodata] = np.nan
        arr[arr < -500] = np.nan
        res_x, res_y = abs(src.transform.a), abs(src.transform.e)
        dy_m = res_y * METERS_PER_DEGREE
        for s in stations.itertuples():
            if not (src.bounds.left <= s.lon <= src.bounds.right and src.bounds.bottom <= s.lat <= src.bounds.top):
                continue
            r, c = src.index(s.lon, s.lat)
            dx_m = res_x * METERS_PER_DEGREE * math.cos(math.radians(s.lat))
            if r < 1 or c < 1 or r >= arr.shape[0] - 1 or c >= arr.shape[1] - 1:
                continue
            z = arr[r - 1:r + 2, c - 1:c + 2]
            elev = float(np.nanmean(z)) if np.isfinite(z).any() else np.nan
            if np.isfinite(z).all():
                dzdx = ((z[0, 2] + 2 * z[1, 2] + z[2, 2]) - (z[0, 0] + 2 * z[1, 0] + z[2, 0])) / (8 * dx_m)
                dzdy = ((z[2, 0] + 2 * z[2, 1] + z[2, 2]) - (z[0, 0] + 2 * z[0, 1] + z[0, 2])) / (8 * dy_m)
                slope = math.degrees(math.atan(math.hypot(dzdx, dzdy)))
            else:
                slope = np.nan
            rel = {}
            for meters in (500, 1000):
                low = window_stats(arr, r, c, int(round(meters / dy_m)))
                rel[meters] = elev - low if np.isfinite(low) and np.isfinite(elev) else np.nan
            rows.append({"station_id": s.station_id, "fabdem_elev_m": elev, "fabdem_slope_deg": slope,
                         "fabdem_relief_500m": rel[500], "fabdem_relief_1km": rel[1000]})
    return pd.DataFrame(rows, columns=["station_id", "fabdem_elev_m", "fabdem_slope_deg", "fabdem_relief_500m", "fabdem_relief_1km"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bbox", type=float, nargs=4, required=True, metavar=("LON_MIN", "LAT_MIN", "LON_MAX", "LAT_MAX"))
    parser.add_argument("--margin", type=float, default=0.05, help="margin (derajat) di sekitar bbox")
    parser.add_argument("--version", default="V1-2")
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--contact", default="ISI-EMAILMU")
    parser.add_argument("--check", action="store_true", help="hanya cek dukungan Range dan isi arsip (membaca daftar isi saja)")
    args = parser.parse_args()

    lon_min, lat_min, lon_max, lat_max = args.bbox
    bbox = (lon_min - args.margin, lat_min - args.margin, lon_max + args.margin, lat_max + args.margin)
    plan = plan_tiles(bbox)
    for block, tiles in plan.items():
        print(f"arsip {block}_FABDEM_{args.version}.zip -> ubin {tiles}")

    session = requests.Session()
    session.headers["User-Agent"] = f"AGC2027-peat-research (kontak: {args.contact})"
    tile_dir = path("raw") / "dem" / "fabdem_tiles"
    tile_dir.mkdir(parents=True, exist_ok=True)
    local = []
    for block, tiles in plan.items():
        url = args.base_url.rstrip("/") + f"/{block}_FABDEM_{args.version}.zip"
        todo = [t for t in tiles if not list(tile_dir.glob(f"*{t}*.tif"))]
        local += [p for t in tiles for p in tile_dir.glob(f"*{t}*.tif")]
        if not todo and not args.check:
            print(f"  {block}: semua ubin sudah ada di cache")
            continue
        zf, size = open_remote_zip(url, session)
        names = zf.namelist()
        print(f"  {block}: ukuran arsip {size / 1e9:.2f} GB | {len(names)} berkas | Range didukung")
        for t in tiles:
            member = find_member(zf, t)
            print(f"    ubin {t}: {'ada' if member else 'TIDAK ADA di arsip (mungkin laut)'}")
        if args.check:
            continue
        for t in todo:
            member = find_member(zf, t)
            if member is None:
                continue
            target = tile_dir / Path(member).name
            target.write_bytes(zf.read(member))
            print(f"    tersimpan {target.name} ({target.stat().st_size / 1e6:.1f} MB)")
            local.append(target)
    if args.check:
        print("(--check: tidak ada ubin yang diunduh)")
        return
    if not local:
        sys.exit("Tidak ada ubin untuk bbox ini (semua laut, atau nama ubin berbeda). Jalankan dengan --check.")

    sources = [rasterio.open(p) for p in sorted(set(local))]
    mosaic, transform = merge(sources, bounds=bbox)
    profile = sources[0].profile | {"height": mosaic.shape[1], "width": mosaic.shape[2], "transform": transform,
                                    "compress": "lzw", "count": 1}
    for s in sources:
        s.close()
    out_tif = path("raw") / "dem" / "fabdem_pilot.tif"
    with rasterio.open(out_tif, "w", **profile) as dst:
        dst.write(mosaic[0], 1)
    print(f"klip bbox: {out_tif} ({mosaic.shape[2]} x {mosaic.shape[1]} piksel)")

    st = add_region(pd.read_parquet(path("interim") / "stations.parquet"))
    st = st[st["coord_ok"] & st["region_ok"]]
    feats = station_features(st, out_tif)
    feats.to_parquet(path("features") / "dem_fabdem.parquet", index=False)
    print(f"fitur medan: {len(feats)} stasiun di dalam bbox -> data/features/dem_fabdem.parquet")
    if len(feats):
        print(feats.describe().loc[["min", "50%", "max"]].round(2).to_string())
    print("\nIngat atribusi: FABDEM is produced using Copernicus WorldDEM-30 (c) DLR e.V.; CC BY-NC-SA 4.0.")


if __name__ == "__main__":
    main()
