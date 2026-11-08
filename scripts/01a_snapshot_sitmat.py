"""01a: ambil satu potret seluruh jaringan stasiun SiTMAT dan simpan mentah (gzip) bertanggal.

    python scripts/01a_snapshot_sitmat.py --contact emailmu@contoh.com

Jendela data di server bergulir 30 hari, jadi jalankan tiap 1-2 minggu agar riwayat menumpuk.
Satu permintaan per potret (sekitar 6,5 MB). Tidak melewati login atau pembatasan apa pun.
"""
import argparse
import gzip
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import path  # noqa: E402

DEFAULT_URL = "https://sitmat.kemenlh.go.id/api/air-gambut"


def fetch(url: str, user_agent: str, retries: int = 3, timeout: int = 180) -> bytes:
    headers = {"User-Agent": user_agent, "Accept": "application/json"}
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
        except requests.RequestException as err:
            print(f"percobaan {attempt + 1}: {err}")
            time.sleep(5 * 2 ** attempt)
            continue
        if resp.status_code == 429 or resp.status_code >= 500:
            wait = float(resp.headers.get("Retry-After", 10 * 2 ** attempt))
            print(f"percobaan {attempt + 1}: HTTP {resp.status_code}, menunggu {wait:.0f} detik")
            time.sleep(wait)
            continue
        resp.raise_for_status()  # 401/403 dll: berhenti, jangan dipaksa
        return resp.content
    sys.exit("Gagal mengambil data setelah beberapa percobaan.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--contact", required=True, help="email kontak untuk User-Agent")
    parser.add_argument("--url", default=DEFAULT_URL)
    args = parser.parse_args()

    content = fetch(args.url, f"AGC2027-peat-research (kontak: {args.contact})")
    data = json.loads(content)
    features = data.get("features", []) if isinstance(data, dict) else []
    if data.get("type") != "FeatureCollection" or not features:
        sys.exit("Respons bukan FeatureCollection yang berisi stasiun; tidak disimpan.")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    out_dir = path("raw") / "sitmat" / "snapshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"stations_{stamp}Z.json.gz"
    with gzip.open(out, "wt", encoding="utf-8") as fh:
        fh.write(content.decode("utf-8"))

    active = sum(1 for f in features if f["properties"].get("detail", {}).get("ListTableLineData"))
    print(f"Tersimpan: {out} | {len(content) / 1e6:.1f} MB | stasiun {len(features)} | punya data {active}")


if __name__ == "__main__":
    main()
