"""18_score_prospective: nilai prediksi yang SUDAH DITERBITKAN (arsip) terhadap kejadian sesudahnya, dan uji indeks kerentanan dengan muka air lapangan.

    python scripts/18_score_prospective.py [--min-issues 20] [--months 6 7 8 9 10 11]

Masuk : outputs/arsip/*/fire_prob_<tanggal_terbit>.parquet (archive_run.py), data/features/event_ledger.parquet (17),
        opsional data/features/fire_cell_day.parquet (13), outputs/tugas/*.parquet (19), data/interim/reports.parquet (16), data/features/grid/risk_index.tif (08)
Keluar: outputs/prospective_scores.json    tiga bagian di bawah
        outputs/prospective_by_issue.csv   per tanggal terbit dan horizon: jumlah sel, positif, sel teratas yang kena

1. Peluang titik api. Untuk terbitan t dan horizon h, kenyataan = kejadian di sel pada t+1..t+h; hanya terbitan yang jendelanya sudah lengkap dinilai.
   Tiga definisi kenyataan: `viirs` (sama dengan label latih), `buku` (VIIRS atau laporan A/B: menambah kejadian yang lolos dari satelit),
   `lapangan` (hanya sel yang benar-benar diperiksa: kejadian A/B lawan nihil A/B; kecil dan bias ke sel yang dikunjungi).
   Tiap definisi juga dihitung TANPA sel bertindakan (pembasahan, pemadaman, perbaikan sekat pada t..t+h): peringatan yang berhasil membuat model tampak salah.
   Pembanding: klimatologi sel-bulan yang ikut diarsipkan (p<h>_klim). lolos_prospektif butuh >= --min-issues terbitan, PR-AUC di atas klimatologi, skill Brier > 0.
2. Tugas pemeriksaan (19): pangsa tugas yang diperiksa, dan laju kejadian pada tugas `teratas` lawan `acak` (uji Fisher). Ini bukti paling langsung
   bahwa peringkat model berguna, karena sel acak diperiksa dengan cara yang sama.
3. Muka air lapangan lawan indeks kerentanan: korelasi peringkat (Spearman) antara indeks di titik dan median muka air musim kering per titik.
   Asumsi 08: indeks lebih tinggi = muka air lebih dalam (lebih negatif), jadi rho diharapkan NEGATIF. Selang 95% dari bootstrap titik.
Laporan tiruan (sumber `tiruan`) ditandai di keluaran: hasilnya hanya menguji alur.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact, spearmanr
from sklearn.metrics import average_precision_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import path  # noqa: E402
from src.reports import KEJADIAN  # noqa: E402


def score(df: pd.DataFrame, y_col: str, top_frac: float) -> dict:
    d = df[df[y_col].notna()]
    y, p, pk = d[y_col].to_numpy(dtype=float), d["p"].to_numpy(), d["pk"].to_numpy()
    out = {"n_terbitan": int(d["issue"].nunique()), "n_sel_terbitan": int(len(d)), "n_positif": int(y.sum())}
    if not 0 < y.sum() < len(y):
        return out | {"catatan": "positif nol atau semua; belum bisa dinilai"}
    brier = lambda q: float(np.mean((q - y) ** 2))
    top = d[d["rank_frac"] <= top_frac]
    return out | {"pr_auc_model": round(float(average_precision_score(y, p)), 4), "pr_auc_klimatologi": round(float(average_precision_score(y, pk)), 4),
                  "brier_model": round(brier(p), 6), "brier_klimatologi": round(brier(pk), 6), "skill_brier_vs_klimatologi": round(1 - brier(p) / brier(pk), 4) if brier(pk) else None,
                  f"tangkapan_{top_frac:.0%}_teratas": round(float(top[y_col].sum() / y.sum()), 4)}


def fire_part(arsip: Path, led: pd.DataFrame, cell_day, data_through, args) -> tuple:
    files = {f.stem.removeprefix("fire_prob_"): f for f in sorted(arsip.glob("*/fire_prob_*.parquet"))}     # arsip terbaru menang per tanggal terbit
    viirs = cell_day[cell_day["n"] > 0][["cell_id", "date"]] if cell_day is not None else led[led["y_viirs"] == 1][["cell_id", "date"]]
    buku = pd.concat([viirs, led[led["y_buku"] == 1][["cell_id", "date"]]])
    lap, act = led[led["y_lapangan"].notna()][["cell_id", "date", "y_lapangan"]], led[led["n_tindakan"] > 0][["cell_id", "date"]]
    rows, skipped = {}, 0
    for issue_s, f in sorted(files.items()):
        prob, issue = pd.read_parquet(f), pd.Timestamp(issue_s)
        for h in sorted(int(c[1:]) for c in prob.columns if c.startswith("p") and c[1:].isdigit()):
            end = issue + pd.Timedelta(days=h)
            if end > data_through:
                skipped += 1
                continue
            win = lambda d, start=issue + pd.Timedelta(days=1): d[d["date"].between(start, end)]
            d = pd.DataFrame({"issue": issue_s, "cell_id": prob["cell_id"], "p": prob[f"p{h}"], "pk": prob[f"p{h}_klim"],
                              "rank_frac": prob[f"p{h}"].rank(ascending=False, method="first") / len(prob)})
            d["viirs"] = d["cell_id"].isin(win(viirs)["cell_id"]).astype(float)
            d["buku"] = d["cell_id"].isin(win(buku)["cell_id"]).astype(float)
            d["lapangan"] = d["cell_id"].map(win(lap).groupby("cell_id")["y_lapangan"].max())
            d["tindakan"] = d["cell_id"].isin(win(act, issue)["cell_id"])
            rows.setdefault(h, []).append(d)
    res, by_issue = {}, []
    for h, parts in rows.items():
        d = pd.concat(parts, ignore_index=True)
        r = {"n_sel_bertindakan": int(d["tindakan"].sum())}
        for y_col in ("viirs", "buku", "lapangan"):
            r[y_col] = score(d, y_col, args.top_frac)
            r[y_col + "_tanpa_sel_bertindakan"] = score(d[~d["tindakan"]], y_col, args.top_frac)
        v = r["viirs"]
        r["lolos_prospektif"] = bool(v["n_terbitan"] >= args.min_issues and v.get("pr_auc_model", 0) > v.get("pr_auc_klimatologi", 1) and (v.get("skill_brier_vs_klimatologi") or 0) > 0)
        res[f"h{h}"] = r
        top = d["rank_frac"] <= args.top_frac
        g = d.assign(buku_teratas=d["buku"].where(top, 0), diperiksa=d["lapangan"].notna()).groupby("issue")
        by_issue.append(g.agg(n_sel=("p", "size"), viirs=("viirs", "sum"), buku=("buku", "sum"), buku_di_teratas=("buku_teratas", "sum"), sel_diperiksa=("diperiksa", "sum"),
                              sel_bertindakan=("tindakan", "sum")).reset_index().assign(horizon=h))
    return res, pd.concat(by_issue, ignore_index=True) if by_issue else pd.DataFrame(), len(files), skipped


def task_part(task_dir: Path, rep: pd.DataFrame) -> dict:
    files = sorted(task_dir.glob("tugas_*.parquet")) if task_dir.exists() else []
    if not files or rep is None:
        return {"catatan": "belum ada daftar tugas (19) atau laporan (16)"}
    tasks = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    done = rep[rep["id_tugas"].notna() & rep["jenis"].isin(KEJADIAN + ("nihil",))].assign(kejadian=lambda d: d["jenis"].isin(KEJADIAN)).groupby("id_tugas")["kejadian"].max()
    tasks["diperiksa"], tasks["kejadian"] = tasks["id_tugas"].isin(done.index), tasks["id_tugas"].map(done).fillna(False).astype(bool)
    out = {"n_tugas": int(len(tasks)), "n_terbitan": len(files), "per_alasan": {}}
    for alasan, g in tasks.groupby("alasan"):
        n, k = int(g["diperiksa"].sum()), int(g["kejadian"].sum())
        out["per_alasan"][alasan] = {"tugas": int(len(g)), "diperiksa": n, "kejadian": k, "laju_kejadian": round(k / n, 4) if n else None}
    a, b = out["per_alasan"].get("teratas"), out["per_alasan"].get("acak")
    if a and b and a["diperiksa"] and b["diperiksa"]:
        out["fisher_teratas_lebih_besar_dari_acak_p"] = round(float(fisher_exact([[a["kejadian"], a["diperiksa"] - a["kejadian"]], [b["kejadian"], b["diperiksa"] - b["kejadian"]]], alternative="greater")[1]), 4)
    return out


def water_part(rep: pd.DataFrame, risk_tif: Path, months, min_readings: int, min_points: int) -> dict:
    if rep is None or not risk_tif.exists():
        return {"catatan": "butuh reports.parquet (16) dan risk_index.tif (08)"}
    import rasterio
    from pyproj import Transformer
    w = rep[(rep["jenis"] == "muka_air") & rep["date"].dt.month.isin(months)].copy()
    if w.empty:
        return {"catatan": "belum ada bacaan muka air pada bulan yang dipilih"}
    with rasterio.open(risk_tif) as src:
        x, y = Transformer.from_crs(4326, src.crs, always_xy=True).transform(w["lon"].to_numpy(), w["lat"].to_numpy())
        w["indeks"] = np.array([v[0] for v in src.sample(zip(x, y))], dtype=float)
    w["titik"] = w["titik_acuan"].fillna(w["lon"].round(3).astype(str) + "_" + w["lat"].round(3).astype(str))
    per = w.groupby("titik").agg(indeks=("indeks", "median"), muka_air_cm=("muka_air_cm", "median"), n=("jenis", "size"))
    per = per[(per["n"] >= min_readings) & per["indeks"].notna()]
    out = {"n_bacaan": int(len(w)), "n_titik_dipakai": int(len(per)), "bulan": list(months), "min_bacaan_per_titik": min_readings, "harapan": "rho negatif (indeks tinggi = muka air lebih dalam)"}
    if len(per) < min_points or per["indeks"].nunique() < 3:
        return out | {"catatan": f"titik terlalu sedikit atau indeks tak bervariasi (butuh >= {min_points} titik); belum bisa menguji indeks"}
    rho, pval = spearmanr(per["indeks"], per["muka_air_cm"])
    rng, a = np.random.default_rng(7), per[["indeks", "muka_air_cm"]].to_numpy()
    boot = np.array([spearmanr(*a[rng.integers(0, len(a), len(a))].T)[0] for _ in range(2000)])
    lo, hi = np.nanpercentile(boot, [2.5, 97.5])
    verdict = "arah sesuai asumsi" if hi < 0 else ("arah BERLAWANAN dengan asumsi" if lo > 0 else "belum terbukti (selang memuat nol)")
    return out | {"spearman_rho": round(float(rho), 3), "p": round(float(pval), 4), "selang_95": [round(float(lo), 3), round(float(hi), 3)], "kesimpulan": verdict,
                  "catatan": "korelasi antar-titik; tidak mengoreksi beda tanggal bacaan, kedalaman gambut, atau sekat. Bahan menyetel bobot 08, bukan bukti sebab-akibat."}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--top-frac", type=float, default=0.05); ap.add_argument("--min-issues", type=int, default=20)
    ap.add_argument("--months", type=int, nargs="+", default=[6, 7, 8, 9, 10, 11]); ap.add_argument("--min-readings", type=int, default=3); ap.add_argument("--min-points", type=int, default=10)
    ap.add_argument("--data-through", help="tanggal terakhir data kejadian yang lengkap (bawaan: tanggal terakhir titik api, atau buku besar)")
    args = ap.parse_args()
    outputs, feats = path("outputs"), path("features")
    led_file = feats / "event_ledger.parquet"
    if not led_file.exists():
        sys.exit(f"{led_file} tidak ada. Jalankan 17_event_ledger.py dulu.")
    led = pd.read_parquet(led_file)
    cell_day = pd.read_parquet(feats / "fire_cell_day.parquet", columns=["cell_id", "date", "n"]) if (feats / "fire_cell_day.parquet").exists() else None
    rep = pd.read_parquet(path("interim") / "reports.parquet") if (path("interim") / "reports.parquet").exists() else None
    data_through = pd.Timestamp(args.data_through) if args.data_through else (cell_day if cell_day is not None else led)["date"].max()

    fire, by_issue, n_files, skipped = fire_part(outputs / "arsip", led, cell_day, data_through, args)
    res = {"dibuat": datetime.now(timezone.utc).isoformat(timespec="seconds"), "data_kejadian_sampai": str(data_through.date()),
           "berisi_data_tiruan": bool(led["tiruan"].any()), "arsip_terbitan": n_files, "terbitan_horizon_belum_lengkap": skipped,
           "titik_api": fire or {"catatan": "belum ada arsip fire_prob yang jendelanya lengkap (jalankan archive_run.py tiap terbit)"},
           "tugas_pemeriksaan": task_part(outputs / "tugas", rep),
           "muka_air_vs_indeks": water_part(rep, feats / "grid" / "risk_index.tif", args.months, args.min_readings, args.min_points)}
    (outputs / "prospective_scores.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    if len(by_issue):
        by_issue.to_csv(outputs / "prospective_by_issue.csv", index=False)

    print(f"arsip: {n_files} terbitan | data kejadian sampai {data_through.date()} | terbitan-horizon belum lengkap: {skipped}")
    for h, r in fire.items():
        for y_col in ("viirs", "buku", "lapangan"):
            s = r[y_col]
            line = f"PR-AUC {s['pr_auc_model']:.3f} (klim {s['pr_auc_klimatologi']:.3f}) | skill Brier {s['skill_brier_vs_klimatologi']:+.3f}" if "pr_auc_model" in s else s["catatan"]
            print(f"  {h} {y_col:9s} terbitan {s['n_terbitan']:>3} | positif {s['n_positif']:>5} dari {s['n_sel_terbitan']:>8,} | {line}")
        print(f"  {h} lolos_prospektif = {r['lolos_prospektif']} | sel bertindakan {r['n_sel_bertindakan']}")
    print("tugas:", json.dumps(res["tugas_pemeriksaan"], ensure_ascii=False))
    print("muka air vs indeks:", json.dumps(res["muka_air_vs_indeks"], ensure_ascii=False))
    if res["berisi_data_tiruan"]:
        print("PERINGATAN: memuat laporan TIRUAN; angka di atas hanya menguji alur, BUKAN bukti kinerja.")


if __name__ == "__main__":
    main()
