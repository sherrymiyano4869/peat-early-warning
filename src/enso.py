"""Pembaca indeks ENSO/IOD dari berkas teks (format standar PSL, ONI CPC, sstoi CPC)."""
from pathlib import Path

import numpy as np
import pandas as pd

SEASON_CENTER = {"DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4, "AMJ": 5, "MJJ": 6,
                 "JJA": 7, "JAS": 8, "ASO": 9, "SON": 10, "OND": 11, "NDJ": 12}


def read_psl_standard(file) -> pd.Series:
    """Format standar PSL: baris tahun diikuti 12 nilai bulanan; nilai <= -90 dianggap hilang."""
    rows = {}
    for line in Path(file).read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) == 13 and parts[0].isdigit() and 1800 <= int(parts[0]) <= 2200:
            try:
                values = [float(x) for x in parts[1:]]
            except ValueError:
                continue
            for month, v in enumerate(values, 1):
                rows[pd.Timestamp(int(parts[0]), month, 1)] = np.nan if v <= -90 else v
    return pd.Series(rows, dtype=float).sort_index()


def read_cpc_oni(file) -> pd.Series:
    """oni.ascii.txt dari CPC: kolom SEAS YR TOTAL ANOM; musim dipetakan ke bulan tengahnya."""
    rows = {}
    for line in Path(file).read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[0] in SEASON_CENTER and parts[1].isdigit():
            rows[pd.Timestamp(int(parts[1]), SEASON_CENTER[parts[0]], 1)] = float(parts[3])
    return pd.Series(rows, dtype=float).sort_index()


def read_cpc_sstoi(file) -> pd.Series:
    """sstoi.indices dari CPC: YR MON NINO1+2 ANOM NINO3 ANOM NINO4 ANOM NINO3.4 ANOM; kembalikan anomali Nino 3.4."""
    rows = {}
    for line in Path(file).read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) == 10 and parts[0].isdigit() and parts[1].isdigit():
            rows[pd.Timestamp(int(parts[0]), int(parts[1]), 1)] = float(parts[9])
    return pd.Series(rows, dtype=float).sort_index()


def load_enso_table(raw_dir) -> pd.DataFrame:
    """Gabungkan berkas yang ada di raw_dir menjadi tabel bulanan: nino34, oni, dmi (kolom hilang bila berkasnya tak ada).

    Prioritas nino34: berkas PSL (nino34*) > sstoi CPC. ONI dari oni.ascii.txt. DMI dari berkas PSL (dmi*).
    """
    raw_dir, series = Path(raw_dir), {}
    psl_nino = sorted(raw_dir.glob("nino34*")) + sorted(raw_dir.glob("Nino34*"))
    if psl_nino:
        series["nino34"] = read_psl_standard(psl_nino[0])
    elif (raw_dir / "sstoi.indices").exists():
        series["nino34"] = read_cpc_sstoi(raw_dir / "sstoi.indices")
    if (raw_dir / "oni.ascii.txt").exists():
        series["oni"] = read_cpc_oni(raw_dir / "oni.ascii.txt")
    dmi = sorted(raw_dir.glob("dmi*")) + sorted(raw_dir.glob("DMI*"))
    if dmi:
        series["dmi"] = read_psl_standard(dmi[0])
    if not series:
        return pd.DataFrame(columns=["date"])
    table = pd.DataFrame(series).rename_axis("date").reset_index()
    return table.sort_values("date").reset_index(drop=True)


def lagged_for_dates(dates: pd.Series, enso: pd.DataFrame, lag_months: int = 1) -> pd.DataFrame:
    """Nilai bulanan ENSO/IOD untuk tiap tanggal, memakai bulan yang sudah selesai (tanpa kebocoran).

    Tanggal pada bulan m memakai nilai bulan m - lag_months (indeks bulanan baru terbit setelah bulan berakhir).
    """
    months = dates.dt.to_period("M").dt.to_timestamp() - pd.DateOffset(months=lag_months)
    base = enso.set_index("date")
    out = pd.DataFrame({"_m": months.to_numpy()})
    for col in base.columns:
        out[col] = base[col].reindex(out["_m"]).to_numpy()
    return out.drop(columns="_m")
