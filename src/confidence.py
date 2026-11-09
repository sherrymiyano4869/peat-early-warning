"""Kepercayaan peta prediksi: komponen, skor 'rantai terlemah', kelas, dan faktor pembatas.

Prinsip: kepercayaan sebuah sel dibatasi oleh komponen terlemahnya (min, bukan rata-rata), karena data berkualitas tinggi tidak
menutupi sel yang jauh dari stasiun atau berada di luar rentang data latih. Semua ambang adalah nilai awal yang bisa disetel,
bukan angka dari literatur.

Komponen (0..1, 1 = sangat dipercaya):
  jarak    : dukungan stasiun (jarak ke stasiun terdekat dan jumlah stasiun dalam 10 km)
  aoa      : kemiripan fitur sel dengan fitur stasiun latih (area of applicability)
  data     : kelengkapan masukan dinamis (bagian fitur yang hilang, mis. NDMI tertutup awan) dan umur komposit terbaru
  interval : lebar rentang prediksi q10-q90 dibanding rujukan dari validasi
Batas dari validasi: kelas akhir tidak boleh lebih tinggi daripada yang dibolehkan bukti skill model (cap_from_skill).
"""
import numpy as np

NAMES_ID = {"jarak": "jarak ke stasiun", "aoa": "di luar rentang data latih", "data": "masukan hilang atau usang", "interval": "rentang prediksi lebar"}
CLASS_LABEL = {0: "rendah", 1: "sedang", 2: "tinggi"}


def cap_from_skill(skill, low=0.0, high=0.10) -> int:
    """Kelas tertinggi yang dibolehkan: skill <= low -> rendah (0); <= high -> sedang (1); selain itu tinggi (2)."""
    if skill is None or not np.isfinite(skill) or skill <= low:
        return 0
    return 1 if skill <= high else 2


def combine_confidence(dist_km, n_stations_10km, aoa_di, aoa_threshold, nan_fraction=None, data_age_days=None,
                       interval_width=None, width_ref=None, max_class=2, d_max=20.0, n_full=3, high=0.67, low=0.33):
    dist_km, n_st, di = (np.asarray(x, dtype=float) for x in (dist_km, n_stations_10km, aoa_di))
    comps = {"jarak": 0.5 * np.clip(1 - dist_km / d_max, 0, 1) + 0.5 * np.clip(n_st / n_full, 0, 1),
             "aoa": np.where(np.isfinite(di), np.where(di <= aoa_threshold, 1.0, np.clip(1 - (di - aoa_threshold) / aoa_threshold, 0, 1)), 0.0)}
    if nan_fraction is not None or data_age_days is not None:
        completeness = 1 - np.asarray(nan_fraction if nan_fraction is not None else 0.0, dtype=float)
        age = np.asarray(data_age_days if data_age_days is not None else 0.0, dtype=float)
        comps["data"] = np.clip(completeness, 0, 1) * np.clip(1 - np.maximum(age - 12, 0) / 48, 0.3, 1)
    if interval_width is not None and width_ref:
        comps["interval"] = np.clip(1 - np.asarray(interval_width, dtype=float) / (2 * width_ref), 0, 1)
    names = list(comps)
    stack = np.stack([np.broadcast_to(comps[n], dist_km.shape) for n in names])
    score = stack.min(axis=0)
    cls = np.minimum(np.where(score >= high, 2, np.where(score >= low, 1, 0)), max_class)
    return {"score": score, "class": cls.astype(int), "limiting": stack.argmin(axis=0), "names": names, "components": comps}
