"""12_fetch_firms: ambil titik api VIIRS 375 m dari NASA FIRMS ke data/raw/firms/ (lapisan L0: bertanggal, tak pernah ditimpa).

Dua mode:
  area    API area FIRMS dengan MAP_KEY gratis (cukup email; daftar di firms.modaps.eosdis.nasa.gov/api/map_key):
          FIRMS_MAP_KEY=... python scripts/12_fetch_firms.py --source VIIRS_SNPP_SP --start 2019-01-01 --end 2019-12-31
          Sumber: VIIRS_SNPP_SP (data sains, untuk melatih), VIIRS_SNPP_NRT / VIIRS_NOAA20_NRT / VIIRS_NOAA21_NRT (hampir waktu nyata, untuk harian).
          URL: {base}/api/area/csv/{MAP_KEY}/{SOURCE}/{barat,selatan,timur,utara}/{HARI}/{TANGGAL}
  archive arsip tahunan per negara tanpa kunci (pola URL dari klien pihak ketiga, BELUM diverifikasi terhadap server; periksa dulu):
          python scripts/12_fetch_firms.py --mode archive --country Indonesia --years 2012 2024

Kunci dibaca dari variabel lingkungan FIRMS_MAP_KEY, tidak pernah ditulis ke disk atau manifest (URL dicatat dengan kunci disamarkan).
Jangan memasukkan kata sandi Earthdata ke skrip ini: API area memakai MAP_KEY, bukan kata sandi.
Tiap potongan menjadi satu berkas, dilewati bila sudah ada (lanjut setelah putus); respons yang bukan CSV (mis. kunci tak sah, batas transaksi)
ditolak dan dicatat di rejects.jsonl alih-alih disimpan sebagai data. Catat jenis data (NRT atau SP): NRT diganti data sains dengan jeda beberapa
bulan, sehingga melatih dengan SP lalu melayani dengan NRT menimbulkan pergeseran distribusi.
"""
import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import path  # noqa: E402

BASE_URL = "https://firms.modaps.eosdis.nasa.gov"
SOURCES = ("VIIRS_SNPP_SP", "VIIRS_SNPP_NRT", "VIIRS_NOAA20_SP", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT")
DEFAULT_BBOX = (95.0, -6.5, 119.5, 6.0)   # Sumatra dan Kalimantan
HEADER_RE = re.compile(r"^latitude,longitude", re.I)


def redact(url: str, key: str | None) -> str:
    return url.replace(key, "***") if key else url


def get_text(session, url, key, retries, timeout):
    last = None
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 504):
                last = f"HTTP {r.status_code}"
                time.sleep(2 ** attempt * 2)
                continue
            return r.status_code, r.text
        except requests.RequestException as e:
            last = type(e).__name__
            time.sleep(2 ** attempt * 2)
    raise RuntimeError(f"gagal setelah {retries} percobaan ({last}): {redact(url, key)}")


def write_chunk(out_file: Path, text: str) -> int:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_file.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
        fh.write(text)
    tmp.replace(out_file)   # penulisan atomik: tidak ada berkas setengah jadi
    return max(text.count("\n") - 1, 0)


def log_manifest(root: Path, entry: dict, name: str = "manifest.jsonl") -> None:
    with open(root / name, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def run_area(args, session, root: Path, key: str) -> dict:
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    if end < start:
        sys.exit("--end lebih awal dari --start")
    w, s, e, n = args.bbox
    stats = {"diminta": 0, "dilewati": 0, "disimpan": 0, "ditolak": 0, "baris": 0}
    day = start
    while day <= end:
        days = min(args.days_per_request, (end - day).days + 1)
        out_file = root / args.source / f"{day.isoformat()}_{days}d.csv.gz"
        stats["diminta"] += 1
        if out_file.exists() and not args.force:
            stats["dilewati"] += 1
            day += timedelta(days=days)
            continue
        url = f"{args.base_url}/api/area/csv/{key}/{args.source}/{w},{s},{e},{n}/{days}/{day.isoformat()}"
        status, text = get_text(session, url, key, args.max_retries, args.timeout)
        if status != 200 or not HEADER_RE.match(text.lstrip()):
            stats["ditolak"] += 1
            log_manifest(root, {"source": args.source, "start": day.isoformat(), "days": days, "http_status": status,
                                "alasan": "respons bukan CSV titik api", "cuplikan": text[:120], "url": redact(url, key),
                                "waktu": datetime.now(timezone.utc).isoformat(timespec="seconds")}, "rejects.jsonl")
            print(f"DITOLAK {args.source} {day} ({days} hari): HTTP {status}, {text[:80]!r}")
            if "transaction" in text.lower() or status == 429:
                print("Batas transaksi tercapai; hentikan dan lanjutkan nanti (potongan yang selesai tidak diulang).")
                break
        else:
            rows = write_chunk(out_file, text)
            stats["disimpan"] += 1
            stats["baris"] += rows
            log_manifest(root, {"source": args.source, "product_type": "SP" if args.source.endswith("_SP") else "NRT", "bbox": list(args.bbox),
                                "start": day.isoformat(), "days": days, "rows": rows, "sha256": hashlib.sha256(text.encode()).hexdigest(),
                                "url": redact(url, key), "http_status": status, "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                "file": str(out_file.relative_to(root))})
            print(f"{args.source} {day} +{days}h: {rows} baris")
        day += timedelta(days=days)
        time.sleep(args.sleep)
    return stats


def run_archive(args, session, root: Path) -> dict:
    stats = {"diminta": 0, "dilewati": 0, "disimpan": 0, "ditolak": 0, "baris": 0}
    for year in range(args.years[0], args.years[1] + 1):
        product = args.archive_product
        out_file = root / "archive" / f"{product}_{year}_{args.country}.csv.gz"
        stats["diminta"] += 1
        if out_file.exists() and not args.force:
            stats["dilewati"] += 1
            continue
        url = f"{args.base_url}/data/country/{product}/{year}/{product}_{year}_{args.country}.csv"
        status, text = get_text(session, url, None, args.max_retries, args.timeout)
        if status != 200 or not HEADER_RE.match(text.lstrip()):
            stats["ditolak"] += 1
            log_manifest(root, {"mode": "archive", "year": year, "http_status": status, "alasan": "respons bukan CSV titik api", "cuplikan": text[:120], "url": url,
                                "waktu": datetime.now(timezone.utc).isoformat(timespec="seconds")}, "rejects.jsonl")
            print(f"DITOLAK arsip {year}: HTTP {status}. Pola URL arsip belum diverifikasi; periksa di situs FIRMS (Download > Archive).")
            continue
        rows = write_chunk(out_file, text)
        stats["disimpan"] += 1
        stats["baris"] += rows
        log_manifest(root, {"mode": "archive", "product": product, "product_type": "SP", "country": args.country, "year": year, "rows": rows,
                            "sha256": hashlib.sha256(text.encode()).hexdigest(), "url": url, "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                            "file": str(out_file.relative_to(root))})
        print(f"arsip {product} {year}: {rows} baris")
        time.sleep(args.sleep)
    return stats


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--mode", choices=["area", "archive"], default="area")
    p.add_argument("--source", choices=SOURCES, default="VIIRS_SNPP_SP")
    p.add_argument("--bbox", type=float, nargs=4, metavar=("BARAT", "SELATAN", "TIMUR", "UTARA"), default=DEFAULT_BBOX)
    p.add_argument("--start", default=(datetime.now(timezone.utc).date() - timedelta(days=9)).isoformat())
    p.add_argument("--end", default=datetime.now(timezone.utc).date().isoformat())
    p.add_argument("--days-per-request", type=int, default=5, help="1-10 menurut halaman API FIRMS; 5 aman untuk klien lain")
    p.add_argument("--country", default="Indonesia"); p.add_argument("--years", type=int, nargs=2, metavar=("DARI", "SAMPAI"), default=[2012, 2024])
    p.add_argument("--archive-product", default="viirs-snpp")
    p.add_argument("--base-url", default=BASE_URL)
    p.add_argument("--out", default=str(path("raw") / "firms"))
    p.add_argument("--sleep", type=float, default=1.0); p.add_argument("--timeout", type=int, default=60); p.add_argument("--max-retries", type=int, default=3)
    p.add_argument("--contact", default=os.environ.get("FIRMS_CONTACT", "ISI-EMAIL-KAMU"))
    p.add_argument("--force", action="store_true", help="unduh ulang potongan yang sudah ada (biasanya tidak perlu)")
    args = p.parse_args()
    if not 1 <= args.days_per_request <= 10:
        sys.exit("--days-per-request harus 1-10")
    root = Path(args.out)
    root.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": f"AGC2027-peat-research (kontak: {args.contact})"})
    if args.mode == "area":
        key = os.environ.get("FIRMS_MAP_KEY")
        if not key:
            sys.exit("Set dulu kunci: export FIRMS_MAP_KEY=... (daftar gratis di firms.modaps.eosdis.nasa.gov/api/map_key). Jangan memakai kata sandi Earthdata.")
        stats = run_area(args, session, root, key)
    else:
        stats = run_archive(args, session, root)
    print(f"\nringkasan: potongan diminta {stats['diminta']} | dilewati (sudah ada) {stats['dilewati']} | disimpan {stats['disimpan']} | ditolak {stats['ditolak']} | baris baru {stats['baris']:,}")
    if stats["ditolak"]:
        print("Lihat", root / "rejects.jsonl")


if __name__ == "__main__":
    main()
