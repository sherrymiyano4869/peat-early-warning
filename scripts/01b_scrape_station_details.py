"""01b: ambil `station-detail` untuk stasiun dalam sebuah potret daftar stasiun, ke folder bertanggal per run.

    python scripts/01b_scrape_station_details.py --contact emailmu@contoh.com --limit 3   # uji dulu
    python scripts/01b_scrape_station_details.py --contact emailmu@contoh.com             # stasiun aktif saja
    python scripts/01b_scrape_station_details.py --contact emailmu@contoh.com --all       # semua stasiun

Tiap run menulis ke data/raw/sitmat/details/<YYYYMMDD>/<station_id>_d<days>.json.gz dan TIDAK menimpa run sebelumnya. SiTMAT hanya
menyimpan sekitar 90 hari riwayat harian dan 30 hari data 30 menitan, jadi deret yang lebih panjang hanya didapat dengan menumpuk
run; 01_stations menggabungkan semua run dan membuang duplikat (nilai dari run terbaru menang).
Bawaan hanya stasiun yang punya data 30 menitan di potret (lebih sedikit permintaan); --all untuk semuanya.
Sopan: jeda antar permintaan, bisa dilanjutkan dalam run yang sama, berhenti bila 401/403 atau 5 kegagalan beruntun.
"""
import argparse
import csv
import gzip
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import path  # noqa: E402
from src.polite_http import PoliteClient  # noqa: E402

BASE = "https://sitmat.kemenlh.go.id/api/air-gambut/masyarakat/station-detail"


def latest_snapshot() -> Path:
    files = sorted((path("raw") / "sitmat" / "snapshots").glob("stations_*.json.gz"))
    if not files:
        sys.exit("Belum ada potret daftar stasiun. Jalankan 01a_snapshot_sitmat.py dulu.")
    return files[-1]


def station_ids(snapshot: Path, active_only: bool) -> list:
    opener = gzip.open if str(snapshot).endswith(".gz") else open
    with opener(snapshot, "rt", encoding="utf-8") as fh:
        features = json.load(fh)["features"]
    ids = []
    for feat in features:
        props = feat.get("properties", {})
        sid = props.get("station_id") or props.get("code")
        if not sid or sid in ids:
            continue
        if active_only and not (props.get("detail") or {}).get("ListTableLineData"):
            continue
        ids.append(sid)
    return ids


def read_json_any(file: Path) -> dict:
    opener = gzip.open if file.suffix == ".gz" else open
    with opener(file, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def summarize(ids: list, days: int, out_dir: Path) -> None:
    rows = []
    for sid in ids:
        file = out_dir / f"{sid}_d{days}.json.gz"
        if not file.exists():
            file = out_dir / f"{sid}_d{days}.json"
        if not file.exists():
            continue
        data = read_json_any(file).get("data") or {}
        props = (data.get("properties") or {}).get("properties")
        if not props:
            continue
        detail, hist = props.get("detail", {}), props.get("history", [])
        dates = [h.get("date") for h in hist if h.get("date")]
        rows.append({"station_id": sid, "n_30min": len(detail.get("ListIOTSensorWaterLevel", [])), "n_history": len(hist),
                     "hist_first": min(dates) if dates else None, "hist_last": max(dates) if dates else None,
                     "lat": props.get("latitude"), "lon": props.get("longitude")})
    out = path("interim") / "details_overview.csv"
    with open(out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["station_id"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nRingkasan run: {len(rows)} stasiun tersimpan | punya data 30 menitan {sum(1 for r in rows if r['n_30min'] > 0)} "
          f"| history >= 60 hari {sum(1 for r in rows if r['n_history'] >= 60)}")
    print("Tersimpan:", out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--contact", required=True, help="email kontak untuk User-Agent")
    parser.add_argument("--snapshot", help="potret daftar stasiun (.json.gz); default yang terbaru")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--min-interval", type=float, default=2.0)
    parser.add_argument("--limit", type=int, help="hanya N stasiun pertama (untuk uji)")
    parser.add_argument("--all", action="store_true", help="semua stasiun, bukan hanya yang aktif di potret")
    parser.add_argument("--run-date", default=datetime.now(timezone.utc).strftime("%Y%m%d"), help="nama folder run (YYYYMMDD)")
    parser.add_argument("--no-gzip", action="store_true", help="biarkan berkas .json (tidak dikompres)")
    parser.add_argument("--base", default=BASE)
    args = parser.parse_args()

    snapshot = Path(args.snapshot) if args.snapshot else latest_snapshot()
    ids = station_ids(snapshot, active_only=not args.all)
    if args.limit:
        ids = ids[: args.limit]
    out_dir = path("raw") / "sitmat" / "details" / args.run_date
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Potret: {snapshot.name} | stasiun: {len(ids)} ({'semua' if args.all else 'aktif saja'}) | days={args.days} "
          f"| jeda {args.min_interval}s | run {args.run_date}")

    client = PoliteClient(out_dir, min_interval=args.min_interval, timeout=60,
                          user_agent=f"AGC2027-peat-research (kontak: {args.contact})")
    ok, failures, streak = 0, [], 0
    for i, sid in enumerate(ids, 1):
        stem = f"{sid}_d{args.days}"
        if (out_dir / f"{stem}.json.gz").exists():  # sudah diunduh dalam run ini
            ok += 1
            continue
        try:
            client.get_json(args.base, params={"station_id": sid, "days": args.days, "source": "simatag"}, name=stem)
            if not args.no_gzip:
                raw_file = out_dir / f"{stem}.json"
                with gzip.open(out_dir / f"{stem}.json.gz", "wt", encoding="utf-8") as fh:
                    fh.write(raw_file.read_text(encoding="utf-8"))
                raw_file.unlink()
            ok, streak = ok + 1, 0
        except requests.HTTPError as err:
            code = err.response.status_code if err.response is not None else None
            if code in (401, 403):
                sys.exit(f"HTTP {code}: akses dibatasi. Berhenti; gunakan jalur permintaan data resmi.")
            failures.append((sid, f"HTTP {code}"))
            streak += 1
        except Exception as err:  # noqa: BLE001
            failures.append((sid, str(err)[:80]))
            streak += 1
        if streak >= 5:
            sys.exit("5 kegagalan beruntun; dihentikan. Periksa --base atau koneksi.")
        if i % 10 == 0 or i == len(ids):
            print(f"{i}/{len(ids)} | ok {ok} | gagal {len(failures)}")

    if failures:
        fail_file = out_dir / "_failures.csv"
        with open(fail_file, "w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerows([("station_id", "alasan"), *failures])
        print("Gagal:", len(failures), "->", fail_file)
    summarize(ids, args.days, out_dir)


if __name__ == "__main__":
    main()
