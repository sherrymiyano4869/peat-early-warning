"""Ringkas jaringan stasiun SiTMAT dari daftar stasiun (satu permintaan) dan simpan ikhtisar.

    python scripts/summarize_network.py /tmp/stations.json
Keluaran: data/interim/stations_overview.csv (satu baris per stasiun).
Catatan: pada endpoint daftar stasiun, muka air bersatuan METER (di station-detail: cm).
"""
import gzip
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import path  # noqa: E402


def load(file: str) -> dict:
    opener = gzip.open if file.endswith(".gz") else open
    with opener(file, "rt", encoding="utf-8") as fh:
        raw = json.load(fh)
    if isinstance(raw, dict) and {"url", "fetched_at", "data"} <= raw.keys():
        raw = raw["data"]
    return raw


def num(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df[col], errors="coerce") if col in df else pd.Series(np.nan, index=df.index)


def table_frame(items: list) -> pd.DataFrame:
    df = pd.DataFrame(items)
    if df.empty:
        return df
    df["ts"] = pd.to_datetime(
        df["Tanggal"].astype(str) + " " + df["Jam"].astype(str), format="%d-%b-%Y %H:%M", errors="coerce"
    )
    df["wl_m"], df["soil"], df["rain"] = num(df, "WaterLevel"), num(df, "SoilMoisture"), num(df, "RainFall")
    return df.dropna(subset=["ts"]).sort_values("ts")


def overview_row(feat: dict) -> dict:
    p = feat.get("properties", {})
    coords = (feat.get("geometry") or {}).get("coordinates") or [p.get("longitude"), p.get("latitude")]
    lon, lat = (coords + [None, None])[:2]
    t = table_frame(p.get("detail", {}).get("ListTableLineData", []))
    hist = pd.DataFrame(p.get("history", []))

    row = {
        "code": p.get("code"), "name": p.get("name") or p.get("lokasi"),
        "provinsi": p.get("provinsi") or None, "kabupaten": p.get("kabupaten") or None,
        "status": p.get("status"), "lon": lon, "lat": lat,
        "coord_ok": bool(lon is not None and lat is not None and 90 <= lon <= 142 and -12 <= lat <= 7),
        "n_table": len(t), "n_history": len(hist),
    }
    if len(t):
        row.update(first_ts=t["ts"].min(), last_ts=t["ts"].max(),
                   wl_filled=int(t["wl_m"].notna().sum()), soil_filled=int(t["soil"].notna().sum()),
                   rain_filled=int(t["rain"].notna().sum()),
                   wl_last_m=t["wl_m"].dropna().iloc[-1] if t["wl_m"].notna().any() else np.nan,
                   wl_min_m=t["wl_m"].min(), wl_max_m=t["wl_m"].max(), rain_sum_mm=t["rain"].sum())
        updated = pd.to_datetime(p.get("updated_at"), utc=True, errors="coerce")
        if pd.notna(updated):  # selisih jam lokal data terhadap UTC; petunjuk zona waktu
            row["tz_diff_h"] = round((t["ts"].max() - updated.tz_localize(None)).total_seconds() / 3600 * 2) / 2
    if len(hist):
        row["hist_first"] = hist["date"].min() if "date" in hist else None
        row["hist_last"] = hist["date"].max() if "date" in hist else None
        row["hist_wl_filled"] = int(num(hist, "water_level").notna().sum())
    return row


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Pemakaian: python scripts/summarize_network.py berkas.json")
    feats = load(sys.argv[1]).get("features", [])
    df = pd.DataFrame([overview_row(f) for f in feats])
    out = path("interim") / "stations_overview.csv"
    df.to_csv(out, index=False)

    active = df["n_table"] > 0
    print(f"stasiun: {len(df)} | punya data 30 menitan: {int(active.sum())} | koordinat tak wajar: {int((~df['coord_ok']).sum())}")
    print("\n== Per status (muka air terakhir dalam meter)")
    print(df.groupby("status").agg(n=("code", "size"), aktif=("n_table", lambda s: int((s > 0).sum())),
                                   wl_min=("wl_last_m", "min"), wl_maks=("wl_last_m", "max")).round(2).to_string())
    print("\n== Per awalan kode")
    print(df.assign(awalan=df["code"].astype(str).str.split("-").str[0]).groupby("awalan")
          .agg(n=("code", "size"), aktif=("n_table", lambda s: int((s > 0).sum()))).to_string())
    print("\n== Provinsi (kosong = None)")
    print(df["provinsi"].value_counts(dropna=False).to_string())
    if active.any():
        a = df[active]
        print("\n== Stasiun aktif")
        print("rentang awal :", a["first_ts"].min(), "->", a["first_ts"].max())
        print("data terakhir:", a["last_ts"].min(), "->", a["last_ts"].max())
        print("titik 30 menitan: min", a["n_table"].min(), "| median", int(a["n_table"].median()), "| maks", a["n_table"].max())
        if "tz_diff_h" in a:
            print("selisih jam lokal-UTC (petunjuk zona waktu):", a["tz_diff_h"].value_counts().to_dict())
        print("muka air terakhir (m): min", round(a["wl_last_m"].min(), 2), "| median", round(a["wl_last_m"].median(), 2),
              "| maks", round(a["wl_last_m"].max(), 2))
        print("hujan 30 hari (mm), jumlah per stasiun: median", round(a["rain_sum_mm"].median(), 1),
              "| maks", round(a["rain_sum_mm"].max(), 1))
    if "hist_first" in df:
        print("\n== history (semua stasiun)")
        print("stasiun dengan history:", int((df["n_history"] > 0).sum()),
              "| baris history median", int(df["n_history"].median()),
              "| awal tertua", df["hist_first"].min(), "| akhir terbaru", df["hist_last"].max())
    print("\nTersimpan:", out)


if __name__ == "__main__":
    main()
