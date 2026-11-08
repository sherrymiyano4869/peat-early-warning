"""Periksa seberapa panjang riwayat dalam respons station-detail.

    python scripts/check_history.py /tmp/s_90.json
Melaporkan isi `history` (ringkasan harian) dan `rows` (rincian per hari).
"""
import json
import sys
from pathlib import Path

import pandas as pd


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Pemakaian: python scripts/check_history.py berkas.json")
    raw = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if isinstance(raw, dict) and {"url", "fetched_at", "data"} <= raw.keys():
        raw = raw["data"]
    props = raw["properties"]["properties"]
    detail = props.get("detail", {})

    print("history_days (sesuai parameter):", props.get("history_days"))

    hist = pd.DataFrame(props.get("history", []))
    print(f"\n== history (ringkasan harian): {len(hist)} baris")
    if len(hist):
        print("rentang:", hist["date"].min(), "->", hist["date"].max())
        for col in ("water_level", "soil_moisture", "rain_fall"):
            if col in hist:
                filled = pd.to_numeric(hist[col], errors="coerce").notna().sum()
                print(f"  {col:<14} terisi {filled}/{len(hist)}")
        print(hist.head(3).to_string(index=False))
        print(hist.tail(3).to_string(index=False))

    rows = detail.get("rows", [])
    print(f"\n== rows (rincian per hari): {len(rows)} baris")
    if rows:
        sizes = [len(r.get("detail", {}).get("ListTableLineData", [])) for r in rows]
        print("rentang:", rows[0].get("data_p2"), "->", rows[-1].get("data_p2"))
        print(f"titik per hari: min {min(sizes)}, median {sorted(sizes)[len(sizes) // 2]}, maks {max(sizes)}")
        filled = next((r for r in rows if r.get("detail", {}).get("ListTableLineData")), None)
        if filled:
            point = filled["detail"]["ListTableLineData"][0]
            print("kunci tiap titik:", list(point.keys()))
            print("contoh titik   :", json.dumps(point, ensure_ascii=False))
        last = rows[-1]
        print("baris terakhir  : gwl =", last.get("gwl"), "| sol =", last.get("sol"), "| chj =", last.get("chj"))


if __name__ == "__main__":
    main()
