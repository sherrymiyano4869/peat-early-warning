"""Skema laporan lapangan: satu sumber untuk formulir XLSForm (tools/build_xlsform.py), pembersihan (16), dan buku besar (17).

Tanda muka air mengikuti SiTMAT: muka_air_cm negatif = di bawah permukaan tanah. Formulir menanyakan "kedalaman" (positif ke bawah) agar mudah diisi.
Identitas pelapor TIDAK disimpan: hanya kode anonim dari koordinator dan kelompok pelapor.
"""
import numpy as np
import pandas as pd

from src.grid import lonlat_to_cell

JENIS = {"api": "Api menyala", "asap": "Asap, nyala tidak terlihat", "membara": "Membara: asap putih dari tanah, bau gambut, tanah hangat, tanpa nyala",
         "nihil": "Sudah diperiksa, tidak ada kejadian", "muka_air": "Bacaan muka air (sumur pantau atau kanal)", "sekat": "Kondisi sekat kanal",
         "tindakan": "Tindakan di lapangan"}
KEJADIAN = ("api", "asap", "membara")
PELAPOR = {"warga": "Warga", "mpa": "Masyarakat Peduli Api", "desa": "Perangkat desa", "bpbd": "BPBD", "manggala_agni": "Manggala Agni"}
PETUGAS = ("bpbd", "manggala_agni")
KONDISI_SEKAT = {"baik": "Baik, menahan air", "rusak": "Rusak, masih menahan sebagian", "jebol": "Jebol, air lolos"}
TINDAKAN = {"pembasahan": "Pembasahan", "pemadaman": "Pemadaman", "perbaikan_sekat": "Perbaikan sekat"}

L1_COLS = ["report_id", "source", "submitted_utc", "observed_utc", "date", "lon", "lat", "gps_acc_m", "jenis", "pelapor", "kode_pelapor", "has_photo",
           "muka_air_cm", "titik_acuan", "kondisi_sekat", "jenis_tindakan", "id_tugas", "flag_gps", "flag_delay", "cx", "cy", "cell_id"]


def _col(df: pd.DataFrame, *names):
    for n in names:
        if n in df.columns:
            return df[n]
    return pd.Series(np.nan, index=df.index, dtype="object")


def _utc(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, utc=True, errors="coerce", format="ISO8601").dt.tz_localize(None)


def _text(s: pd.Series) -> pd.Series:
    return s.astype("string").str.strip().replace("", pd.NA)


def normalize(df: pd.DataFrame, max_gps_m: float = 50.0, max_delay_days: float = 3.0) -> pd.DataFrame:
    """Rekaman mentah (JSON Kobo, ekspor CSV Kobo, atau CSV sekunder berkolom lat/lon) -> kolom L1. Baris tidak dibuang di sini."""
    geo = _col(df, "lokasi").astype("string").str.split(expand=True).reindex(columns=range(4))
    num = lambda s: pd.to_numeric(s, errors="coerce")
    out = pd.DataFrame({
        "report_id": _text(_col(df, "_uuid", "report_id")), "source": df["source"],
        "submitted_utc": _utc(_col(df, "_submission_time", "submitted_utc")), "observed_utc": _utc(_col(df, "waktu_amat")),
        "lon": num(_col(df, "_lokasi_longitude", "lon")).fillna(num(geo[1])), "lat": num(_col(df, "_lokasi_latitude", "lat")).fillna(num(geo[0])),
        "gps_acc_m": num(_col(df, "_lokasi_precision", "gps_acc_m")).fillna(num(geo[3])),
        "jenis": _text(_col(df, "jenis")).str.lower(), "pelapor": _text(_col(df, "pelapor")).str.lower(), "kode_pelapor": _text(_col(df, "kode_pelapor")),
        "has_photo": _text(_col(df, "foto")).notna(), "muka_air_cm": -num(_col(df, "kedalaman_cm")), "titik_acuan": _text(_col(df, "titik_acuan")),
        "kondisi_sekat": _text(_col(df, "kondisi_sekat")).str.lower(), "jenis_tindakan": _text(_col(df, "jenis_tindakan")).str.lower(),
        "id_tugas": _text(_col(df, "id_tugas")).str.upper()})
    out["observed_utc"] = out["observed_utc"].fillna(out["submitted_utc"])
    out["submitted_utc"] = out["submitted_utc"].fillna(out["observed_utc"])
    out["date"] = (out["observed_utc"] + pd.Timedelta(hours=7)).dt.normalize()
    out["flag_gps"] = out["gps_acc_m"] > max_gps_m                       # akurasi tak diketahui tidak ditandai, tetapi juga tidak dihitung "baik" di 17
    out["flag_delay"] = (out["submitted_utc"] - out["observed_utc"]) > pd.Timedelta(days=max_delay_days)
    ok = out["lon"].notna() & out["lat"].notna()
    for c in ("cx", "cy", "cell_id"):
        out[c] = pd.array([pd.NA] * len(out), dtype="Int64")
    if ok.any():
        cx, cy, cid = lonlat_to_cell(out.loc[ok, "lon"].to_numpy(), out.loc[ok, "lat"].to_numpy(), 1000)
        out.loc[ok, "cx"], out.loc[ok, "cy"], out.loc[ok, "cell_id"] = cx, cy, cid
    return out[L1_COLS]
