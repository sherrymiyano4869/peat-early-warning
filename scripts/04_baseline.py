"""04_baseline: baseline dan model awal sensor virtual.

Masuk : data/features/model_table.parquet
Keluar: outputs/metrics.csv dan grafik
Model: klimatologi mingguan, regresi hujan-terdahulu, LightGBM (titik dan kuantil).
Validasi: GroupKFold per khg_id (spasial) dan pemisahan temporal.
Metrik: RMSE, MAE, NSE untuk muka air; Brier dan PR-AUC untuk ambang -30/-40/-50 cm.
"""
raise NotImplementedError("Tulis setelah model_table.parquet tersedia.")
