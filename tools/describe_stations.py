"""Ringkas daftar stasiun SiTMAT (GeoJSON FeatureCollection).

    python scripts/describe_stations.py /tmp/stations.json
    python scripts/describe_stations.py /tmp/stations.json MTI-0QPGP748RCSW
Argumen kedua (opsional) menampilkan isi satu stasiun, untuk membandingkan satuan
dengan respons station-detail.
"""
import gzip
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import median


def load(path: str) -> dict:
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as fh:
        raw = json.load(fh)
    if isinstance(raw, dict) and {"url", "fetched_at", "data"} <= raw.keys():
        raw = raw["data"]
    return raw


def main() -> None:
    args = sys.argv[1:]
    if not args:
        sys.exit("Pemakaian: python scripts/describe_stations.py berkas.json [KODE_STASIUN]")
    fc = load(args[0])
    feats = fc.get("features", [])
    print("tipe:", fc.get("type"), "| jumlah fitur:", len(feats))

    coords = [f["geometry"]["coordinates"] for f in feats if f.get("geometry")]
    if coords:
        lons, lats = [c[0] for c in coords], [c[1] for c in coords]
        print(f"bbox lon {min(lons):.2f}..{max(lons):.2f} | lat {min(lats):.2f}..{max(lats):.2f}")

    prop_keys, detail_keys = Counter(), Counter()
    for f in feats:
        props = f.get("properties", {})
        prop_keys.update(props.keys())
        detail_keys.update(props.get("detail", {}).keys())
    print("kunci properties:", dict(prop_keys))
    print("kunci detail    :", dict(detail_keys))

    codes = [f.get("properties", {}).get("code") for f in feats]
    print("kode unik:", len(set(codes)), "dari", len(codes))
    print("prefiks kode:", dict(Counter(str(c).split("-")[0] for c in codes)))
    for key in ("source", "status", "device_type", "type"):
        values = Counter(str(f["properties"][key]) for f in feats if key in f.get("properties", {}))
        if values:
            print(f"{key}:", dict(values))

    for name in ("ListIOTSensorWaterLevel", "ListIOTSensorSoilMoisture", "ListIOTSensorRainFall"):
        counts = [len(f.get("properties", {}).get("detail", {}).get(name, [])) for f in feats]
        if any(counts):
            print(f"{name}: titik per stasiun min {min(counts)} | median {median(counts)} | maks {max(counts)} "
                  f"| stasiun kosong {sum(1 for c in counts if c == 0)}")

    created = sorted(str(f.get("properties", {}).get("created_at", "")) for f in feats)
    if created:
        print("created_at terlama:", created[0], "| terbaru:", created[-1])

    if len(args) > 1:
        target = next((f for f in feats if f.get("properties", {}).get("code") == args[1]), None)
        if target is None:
            print(f"\nStasiun {args[1]} tidak ditemukan.")
            return
        print(f"\n== {args[1]} | koordinat {target['geometry']['coordinates']}")
        detail = target["properties"].get("detail", {})
        print("Tanggal/Jam di detail:", detail.get("Tanggal"), detail.get("Jam"))
        for name, items in detail.items():
            if isinstance(items, list):
                print(f"{name}: {len(items)} titik")
                for item in items[-3:]:
                    print("   ", json.dumps(item, ensure_ascii=False))


if __name__ == "__main__":
    main()
