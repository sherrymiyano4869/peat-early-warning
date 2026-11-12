"""16_ingest_reports: laporan lapangan (warga, MPA, desa, BPBD, Manggala Agni) -> L0 bertanggal -> laporan bersih (L1) di sel 1 km.

    KOBO_TOKEN=... python scripts/16_ingest_reports.py --kobo-asset UID [--kobo-server https://kf.kobotoolbox.org]
    python scripts/16_ingest_reports.py --csv berkas.csv --source bpbd_sekunder     # ekspor CSV Kobo atau data sekunder berkolom lat, lon
    python scripts/16_ingest_reports.py                                             # hanya bangun ulang L1 dari L0 yang ada

Masuk : formulir forms/laporan_lapangan.xlsx (tools/build_xlsform.py); skema di src/reports.py
Keluar: data/raw/laporan/<sumber>/<waktu>.json.gz|csv.gz + manifest.jsonl   potret tak pernah ditimpa, dengan sha256
        data/interim/reports.parquet                                        satu baris per laporan sah, tanggal WIB, sel 1 km
        data/interim/reports_meta.json                                      pencatatan baris tiap tahap

Token dibaca dari KOBO_TOKEN dan tidak pernah ditulis. Kolom identitas Kobo (nama akun, perangkat, nomor telepon) dibuang SEBELUM disimpan;
foto tidak diunduh (hanya dicatat ada atau tidak). Tiap tarikan Kobo adalah potret penuh; duplikat antar-potret dibuang di L1 (potret terbaru menang).
Laporan dengan GPS buruk atau terlambat dikirim TIDAK dibuang, hanya ditandai (flag_gps, flag_delay) dan diturunkan tingkatnya di 17.
Sumber bernama `tiruan` adalah data buatan (tools/fake_reports.py): hanya untuk menguji alur.
Titik akhir Kobo (api/v2/assets/<uid>/data/?format=json, berhalaman lewat `next`) diuji dengan server tiruan, BELUM dengan server Kobo sungguhan.
"""
import argparse
import gzip
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import path  # noqa: E402
from src.reports import JENIS, normalize  # noqa: E402

IDENTITY_KEYS = ("_submitted_by", "username", "deviceid", "phonenumber", "simserial", "subscriberid", "email", "_attachments", "_validation_status", "_notes")
DEFAULT_BBOX = (95.0, -6.5, 119.5, 6.0)   # Sumatra dan Kalimantan, sama dengan 12


def fetch_kobo(server: str, asset: str, token: str, timeout: int = 60) -> list:
    url, rows = f"{server.rstrip('/')}/api/v2/assets/{asset}/data/?format=json&limit=1000", []
    with requests.Session() as s:
        s.headers["Authorization"] = f"Token {token}"
        while url:
            r = s.get(url, timeout=timeout)
            r.raise_for_status()
            page = r.json()
            rows += page["results"]
            url = page.get("next")
    return [{k: v for k, v in row.items() if k not in IDENTITY_KEYS} for row in rows]


def write_l0(root: Path, source: str, payload: bytes, ext: str, n: int, origin: str) -> Path:
    now = datetime.now(timezone.utc)
    folder = root / source
    folder.mkdir(parents=True, exist_ok=True)
    out, k = folder / f"{now:%Y%m%d_%H%M%SZ}.{ext}.gz", 1
    while out.exists():
        k += 1
        out = folder / f"{now:%Y%m%d_%H%M%SZ}_{k}.{ext}.gz"
    tmp = out.with_suffix(".part")
    tmp.write_bytes(gzip.compress(payload))
    tmp.rename(out)
    with open(root / "manifest.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"file": str(out.relative_to(root)), "source": source, "n": n, "sha256": hashlib.sha256(payload).hexdigest(),
                             "fetched_utc": f"{now:%Y-%m-%dT%H:%M:%SZ}", "origin": origin}, ensure_ascii=False) + "\n")
    return out


def read_l0(root: Path) -> pd.DataFrame:
    frames = []
    for f in sorted(root.glob("*/*.gz")):
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            df = pd.DataFrame(json.load(fh)) if f.name.endswith(".json.gz") else pd.read_csv(fh, dtype=str)
        if len(df):
            frames.append(df.assign(source=f.parent.name, _snapshot=f.name))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--kobo-asset"); p.add_argument("--kobo-server", default="https://kf.kobotoolbox.org")
    p.add_argument("--csv"); p.add_argument("--source", help="nama sumber untuk --csv (mis. bpbd_sekunder, tiruan)")
    p.add_argument("--bbox", type=float, nargs=4, default=DEFAULT_BBOX, metavar=("BARAT", "SELATAN", "TIMUR", "UTARA"))
    p.add_argument("--max-gps-m", type=float, default=50.0); p.add_argument("--max-delay-days", type=float, default=3.0)
    args = p.parse_args()
    root = path("raw") / "laporan"

    if args.kobo_asset:
        token = os.environ.get("KOBO_TOKEN")
        if not token:
            sys.exit("KOBO_TOKEN belum diset (token API dari pengaturan akun KoboToolbox).")
        rows = fetch_kobo(args.kobo_server, args.kobo_asset, token)
        f = write_l0(root, "kobo", json.dumps(rows, ensure_ascii=False).encode(), "json", len(rows), f"{args.kobo_server} aset {args.kobo_asset}")
        print(f"Kobo: {len(rows)} laporan -> {f}")
    if args.csv:
        if not args.source or args.source == "kobo":
            sys.exit("--csv butuh --source NAMA (selain `kobo`).")
        payload = Path(args.csv).read_bytes()
        f = write_l0(root, args.source, payload, "csv", max(payload.count(b"\n") - 1, 0), Path(args.csv).name)
        print(f"CSV: {args.csv} -> {f}")

    raw = read_l0(root)
    if raw.empty:
        sys.exit(f"Belum ada laporan di {root}. Pakai --kobo-asset atau --csv.")
    acc = []

    def stage(name: str, before: int, df: pd.DataFrame, note: str = "") -> pd.DataFrame:
        acc.append({"tahap": name, "masuk": before, "keluar": len(df), "catatan": note})
        return df

    snapshot = raw["_snapshot"]
    rep = stage("baca mentah", len(raw), normalize(raw, args.max_gps_m, args.max_delay_days), f"{snapshot.nunique()} potret, sumber {sorted(raw['source'].unique())}")
    n = len(rep)
    rep = stage("buang tanpa koordinat, waktu, atau jenis sah", n, rep[rep["lon"].notna() & rep["lat"].notna() & rep["observed_utc"].notna() & rep["jenis"].isin(JENIS)])
    n = len(rep)
    w, s, e, nn = args.bbox
    rep = stage("dalam bbox", n, rep[rep["lon"].between(w, e) & rep["lat"].between(s, nn)])
    n = len(rep)
    rep = stage("buang waktu amat di masa depan", n, rep[rep["observed_utc"] <= pd.Timestamp.now(tz="UTC").tz_localize(None) + pd.Timedelta(hours=1)])
    n = len(rep)
    rep = stage("muka air tanpa angka dibuang", n, rep[(rep["jenis"] != "muka_air") | rep["muka_air_cm"].between(-300, 100)])
    n = len(rep)
    key = rep["report_id"].fillna(rep["source"] + "|" + rep["observed_utc"].astype(str) + "|" + rep["lon"].round(5).astype(str) + "|" + rep["lat"].round(5).astype(str) + "|" + rep["jenis"])
    rep = rep.assign(report_id=key, _snap=snapshot.reindex(rep.index)).sort_values("_snap", kind="mergesort").drop_duplicates("report_id", keep="last").drop(columns="_snap")
    rep = stage("buang duplikat (potret terbaru menang)", n, rep.sort_values(["date", "cell_id", "report_id"], kind="mergesort").reset_index(drop=True))

    rep.to_parquet(path("interim") / "reports.parquet", index=False)
    meta = {"accounting": acc, "n": int(len(rep)), "date_min": str(rep["date"].min().date()) if len(rep) else None, "date_max": str(rep["date"].max().date()) if len(rep) else None,
            "per_jenis": rep["jenis"].value_counts().to_dict(), "per_sumber": rep["source"].value_counts().to_dict(), "per_pelapor": rep["pelapor"].value_counts().to_dict(),
            "ditandai_gps": int(rep["flag_gps"].sum()), "ditandai_terlambat": int(rep["flag_delay"].sum()),
            "ambang": {"max_gps_m": args.max_gps_m, "max_delay_days": args.max_delay_days}, "timezone": "tanggal WIB (UTC+7)", "grid": "ESRI:54034, sel 1 km"}
    (path("interim") / "reports_meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    for a in acc:
        print(f"{a['tahap']:46s} {a['masuk']:>7,} -> {a['keluar']:>7,}  {a['catatan']}")
    print(f"\n{len(rep):,} laporan | {meta['date_min']} s/d {meta['date_max']} | jenis {meta['per_jenis']} | ditandai GPS {meta['ditandai_gps']}, terlambat {meta['ditandai_terlambat']}")
    if "tiruan" in meta["per_sumber"]:
        print("PERINGATAN: ada laporan TIRUAN; hasil hilir hanya menguji alur, bukan bukti.")


if __name__ == "__main__":
    main()
