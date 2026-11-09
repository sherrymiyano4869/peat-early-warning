"""02b_enso: susun tabel indeks ENSO dan IOD bulanan dari berkas teks NOAA.

    python scripts/02b_enso.py            # membaca data/raw/enso/
    python scripts/02b_enso.py --auto     # coba unduh berkas CPC lebih dulu (oni.ascii.txt dan sstoi.indices)

Letakkan berkas di data/raw/enso/ :
  nino34.data  : halaman PSL Niño 3.4 -> "Get Data" -> Standard PSL Format (anomali bulanan; ERSST v6 dari CPC)
  dmi.data     : halaman PSL DMI -> "Get Data" -> Standard PSL Format (IOD)
  oni.ascii.txt dan sstoi.indices : dari CPC (bisa diunduh otomatis dengan --auto)
Halaman: https://psl.noaa.gov/enso/dashboard.html (kolom Name memuat tautan tiap indeks).
Keluaran: data/features/enso_monthly.parquet (kolom date, nino34, oni, dmi). Cocokkan nilai terbaru dengan dashboard.
Sumber berbeda (ERSST v6 vs OISST) memberi angka sedikit berbeda; pilih satu dan konsisten.
"""
import argparse
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import path  # noqa: E402
from src.enso import load_enso_table  # noqa: E402

AUTO = {
    "oni.ascii.txt": "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt",
    "sstoi.indices": "https://www.cpc.ncep.noaa.gov/data/indices/sstoi.indices",
}


def download(url: str, target: Path, contact: str) -> bool:
    try:
        resp = requests.get(url, headers={"User-Agent": f"AGC2027-peat-research (kontak: {contact})"}, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as err:
        print(f"  gagal mengunduh {url}: {str(err)[:80]}")
        return False
    target.write_bytes(resp.content)
    print(f"  tersimpan {target.name} ({len(resp.content) / 1e3:.0f} KB)")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--auto", action="store_true", help="coba unduh oni.ascii.txt dan sstoi.indices dari CPC")
    parser.add_argument("--contact", default="ISI-EMAILMU", help="email untuk User-Agent saat --auto")
    args = parser.parse_args()

    raw = path("raw") / "enso"
    raw.mkdir(parents=True, exist_ok=True)
    if args.auto:
        print("Mengunduh dari CPC ...")
        for name, url in AUTO.items():
            download(url, raw / name, args.contact)

    table = load_enso_table(raw)
    if table.empty or len(table.columns) < 2:
        sys.exit(f"Tidak ada berkas ENSO yang terbaca di {raw}. Lihat petunjuk di docstring (nino34.data, dmi.data, ...).")
    table.to_parquet(path("features") / "enso_monthly.parquet", index=False)
    print(f"kolom: {[c for c in table.columns if c != 'date']} | {table['date'].min():%Y-%m} .. {table['date'].max():%Y-%m}")
    last = table.dropna(how="all", subset=[c for c in table.columns if c != "date"]).tail(4)
    print("empat bulan terakhir (cocokkan dengan dashboard PSL):")
    print(last.assign(date=last["date"].dt.strftime("%Y-%m")).round(2).to_string(index=False))
    print("Tersimpan: data/features/enso_monthly.parquet")


if __name__ == "__main__":
    main()
