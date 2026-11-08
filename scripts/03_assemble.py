"""03_assemble: gabungkan label, fitur GEE, ENSO/DMI, dan fitur lokal.

Masuk : stations_weekly.parquet, gee_features.parquet, ONI dan DMI (NOAA),
        kanal RBI dan batas KHG
Keluar: data/features/model_table.parquet, kamus data
Langkah:
  1. Unduh ONI dan DMI, sambungkan per bulan.
  2. Hitung jarak ke kanal dan fitur turunan topografi (geopandas).
  3. Hitung fitur fisik: defisit air kumulatif (ala Drought Code), anomali hujan.
  4. Beri grup spasial (khg_id) dan penanda musim/tahun untuk pemisahan data.
"""
raise NotImplementedError("Tulis setelah fitur GEE tersedia.")
