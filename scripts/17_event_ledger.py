"""17_event_ledger: buku besar kejadian per sel-hari 1 km dari laporan lapangan (16) dan titik api VIIRS (13), dengan tingkat keyakinan A/B/C.

    python scripts/17_event_ledger.py [--radius-m 1000 --window-h 48]

Masuk : data/interim/reports.parquet (16); opsional data/interim/hotspots.parquet (13)
Keluar: data/features/event_ledger.parquet   satu baris per sel-hari yang punya bukti ATAU kunjungan (lihat kolom di bawah)
        data/features/canal_blocks.parquet   kondisi sekat TERAKHIR per titik (bahan indeks struktural; belum dipakai 08)
        data/interim/ledger_meta.json        ringkasan, parameter, dan pangsa kejadian lapangan yang lolos dari VIIRS

Pencocokan: laporan kejadian (api, asap, membara) cocok dengan deteksi VIIRS bila jarak <= --radius-m dan selisih waktu <= --window-h.
Kedua angka itu ANGKA AWAL tanpa sumber; setel dengan data sekunder BPBD sebelum dipakai untuk klaim.
Tingkat keyakinan laporan (bukti terbaik per sel-hari yang dipakai):
  A  cocok dengan VIIRS, atau dari petugas (BPBD, Manggala Agni) dengan foto dan GPS baik
  B  ada foto dengan GPS baik, atau >= 2 pelapor berbeda di sel-hari yang sama
  C  selebihnya (tidak dipakai untuk menilai model)
GPS baik = akurasi tercatat dan <= ambang 16; laporan terlambat dikirim (flag_delay) paling tinggi B.
Kolom label: y_viirs (label latih 14), y_buku (VIIRS atau laporan A/B), y_lapangan (1 = kejadian A/B, 0 = nihil A/B, kosong = sel-hari tak diperiksa).
`n_kunjungan` (semua laporan di sel-hari) adalah catatan UPAYA: tanpa kunjungan, "tidak ada laporan" bukan berarti "tidak ada kejadian".
VIIRS tidak dipakai sebagai bukti NIHIL (awan, asap, dan api membara lolos dari deteksi).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import path  # noqa: E402
from src.grid import to_grid  # noqa: E402
from src.reports import KEJADIAN, PETUGAS  # noqa: E402

TIER = np.array(["C", "B", "A"])


def match_viirs(rep: pd.DataFrame, hot: pd.DataFrame, radius_m: float, window_h: float) -> np.ndarray:
    """Jumlah deteksi VIIRS dalam radius dan jendela waktu tiap laporan."""
    if rep.empty or hot.empty:
        return np.zeros(len(rep), dtype=int)
    tree = cKDTree(np.column_stack(to_grid(hot["lon"].to_numpy(), hot["lat"].to_numpy())))
    near = tree.query_ball_point(np.column_stack(to_grid(rep["lon"].to_numpy(), rep["lat"].to_numpy())), radius_m)
    t_hot, t_rep, win = hot["datetime_utc"].to_numpy(), rep["observed_utc"].to_numpy(), np.timedelta64(int(window_h * 3600), "s")
    return np.array([int((np.abs(t_hot[idx] - t) <= win).sum()) if idx else 0 for idx, t in zip(near, t_rep)])


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--radius-m", type=float, default=1000.0); p.add_argument("--window-h", type=float, default=48.0)
    args = p.parse_args()
    rep_file, hot_file = path("interim") / "reports.parquet", path("interim") / "hotspots.parquet"
    if not rep_file.exists():
        sys.exit(f"{rep_file} tidak ada. Jalankan 16_ingest_reports.py dulu.")
    rep = pd.read_parquet(rep_file)
    hot = pd.read_parquet(hot_file) if hot_file.exists() else pd.DataFrame(columns=["lon", "lat", "date", "datetime_utc", "conf", "cell_id"])
    if hot.empty:
        print("PERINGATAN: hotspots.parquet tidak ada; buku besar hanya dari laporan (tidak ada tingkat A lewat satelit).")

    # ---- tingkat keyakinan per laporan
    rep["kejadian"] = rep["jenis"].isin(KEJADIAN)
    rep["n_match"] = 0
    rep.loc[rep["kejadian"], "n_match"] = match_viirs(rep[rep["kejadian"]], hot, args.radius_m, args.window_h)
    gps_ok = rep["gps_acc_m"].notna() & ~rep["flag_gps"]
    photo_ok = rep["has_photo"] & gps_ok
    tier = np.where((rep["n_match"] > 0) | (photo_ok & rep["pelapor"].isin(PETUGAS)), 2, np.where(photo_ok, 1, 0))
    rep["tier"] = np.where(rep["flag_delay"] & (rep["n_match"] == 0), np.minimum(tier, 1), tier)

    # ---- agregasi sel-hari
    key = ["cell_id", "date"]
    cells = rep.groupby(key).agg(n_kunjungan=("jenis", "size"), n_pelapor=("kode_pelapor", "nunique"), n_tindakan=("jenis", lambda s: int((s == "tindakan").sum())),
                  tiruan=("source", lambda s: bool((s == "tiruan").any())))
    for name, mask in (("pos", rep["kejadian"]), ("nihil", rep["jenis"] == "nihil")):
        sub = rep[mask].groupby(key)
        cells = cells.join(sub.agg(**{f"n_{name}": ("jenis", "size"), f"tier_{name}": ("tier", "max"), f"pelapor_{name}": ("kode_pelapor", "nunique")}))
    cells = cells.join(rep[rep["kejadian"]].groupby(key).agg(n_match=("n_match", "sum"), membara=("jenis", lambda s: bool((s == "membara").any())),
                                                           menyala=("jenis", lambda s: bool((s == "api").any()))))
    viirs = hot.groupby(key).agg(n_viirs=("lon", "size"), viirs_conf=("conf", "max")) if len(hot) else pd.DataFrame(columns=["n_viirs", "viirs_conf"])
    led = cells.join(viirs, how="outer").reset_index()
    count_cols = ["n_kunjungan", "n_pelapor", "n_tindakan", "n_pos", "n_nihil", "n_match", "n_viirs", "pelapor_pos", "pelapor_nihil"]
    led[count_cols] = led[count_cols].fillna(0).astype(int)
    for c in ("membara", "menyala", "tiruan"):
        led[c] = led[c].fillna(False).astype(bool)
    for name in ("pos", "nihil"):   # dua pelapor berbeda menaikkan C menjadi B
        t = led[f"tier_{name}"].fillna(-1).astype(int)
        led[f"tier_{name}"] = np.where((t == 0) & (led[f"pelapor_{name}"] >= 2), 1, t)

    has_rep, has_sat = led["n_pos"] > 0, (led["n_viirs"] > 0) | (led["n_match"] > 0)
    led["sumber"] = np.select([has_rep & has_sat, has_rep, has_sat], ["keduanya", "laporan", "satelit"], default="")
    led["status"] = np.select([has_rep | has_sat, led["n_nihil"] > 0], ["kejadian", "nihil"], default="kunjungan")
    led["konflik"] = (led["n_nihil"] > 0) & (has_rep | has_sat)
    tier_evt = np.where(has_rep, led["tier_pos"], np.where(led["status"] == "nihil", led["tier_nihil"], -1))
    led["tingkat"] = np.where(tier_evt >= 0, TIER[np.clip(tier_evt, 0, 2)], "")
    led["y_viirs"] = (led["n_viirs"] > 0).astype("int8")
    field_pos, field_neg = has_rep & (led["tier_pos"] >= 1), (led["status"] == "nihil") & (led["tier_nihil"] >= 1)
    led["y_buku"] = ((led["n_viirs"] > 0) | field_pos).astype("int8")
    led["y_lapangan"] = np.where(field_pos, 1.0, np.where(field_neg, 0.0, np.nan))
    led = led.drop(columns=["tier_pos", "tier_nihil", "pelapor_pos", "pelapor_nihil"]).sort_values(key, kind="mergesort").reset_index(drop=True)
    led.to_parquet(path("features") / "event_ledger.parquet", index=False)

    # ---- sekat kanal: kondisi terakhir per titik
    sekat = rep[rep["jenis"] == "sekat"].copy()
    sekat["titik"] = sekat["titik_acuan"].fillna(sekat["lon"].round(4).astype(str) + "_" + sekat["lat"].round(4).astype(str))
    sekat = sekat.sort_values("observed_utc").groupby("titik").agg(lon=("lon", "last"), lat=("lat", "last"), kondisi=("kondisi_sekat", "last"),
                                                                    tanggal=("date", "last"), n_laporan=("jenis", "size")).reset_index()
    sekat.to_parquet(path("features") / "canal_blocks.parquet", index=False)

    evt = led[led["status"] == "kejadian"]
    field = evt[evt["y_lapangan"] == 1]
    missed = field[field["n_viirs"] + field["n_match"] == 0]
    meta = {"parameter": {"radius_m": args.radius_m, "window_h": args.window_h, "catatan": "angka awal tanpa sumber; setel dengan data sekunder"},
            "n_sel_hari": int(len(led)), "status": led["status"].value_counts().to_dict(),
            "kejadian_per_sumber_dan_tingkat": {f"{s}|{t or '-'}": int(n) for (s, t), n in evt.groupby(["sumber", "tingkat"]).size().items()},
            "nihil_per_tingkat": led[led["status"] == "nihil"]["tingkat"].value_counts().to_dict(), "konflik": int(led["konflik"].sum()),
            "kejadian_lapangan_AB": int(len(field)), "lolos_dari_viirs": int(len(missed)),
            "pangsa_lolos_dari_viirs": round(len(missed) / len(field), 3) if len(field) else None,
            "lolos_dari_viirs_membara": int(missed["membara"].sum()), "sel_hari_dengan_tindakan": int((led["n_tindakan"] > 0).sum()),
            "titik_sekat": sekat["kondisi"].value_counts().to_dict(), "berisi_data_tiruan": bool(led["tiruan"].any()),
            "rentang": [str(led["date"].min().date()), str(led["date"].max().date())] if len(led) else None}
    (path("interim") / "ledger_meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    print(f"buku besar: {len(led):,} sel-hari | {meta['status']} | konflik {meta['konflik']}")
    print("kejadian per sumber|tingkat:", meta["kejadian_per_sumber_dan_tingkat"])
    if len(field):
        print(f"kejadian lapangan A/B: {len(field)} | lolos dari VIIRS: {len(missed)} ({meta['pangsa_lolos_dari_viirs']:.0%}), di antaranya membara {meta['lolos_dari_viirs_membara']}")
    print(f"titik sekat: {meta['titik_sekat']} | sel-hari bertindakan: {meta['sel_hari_dengan_tindakan']}")
    if meta["berisi_data_tiruan"]:
        print("PERINGATAN: buku besar memuat laporan TIRUAN; hanya menguji alur.")


if __name__ == "__main__":
    main()
