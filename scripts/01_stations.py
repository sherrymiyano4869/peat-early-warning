"""01_stations: baca data stasiun SiTMAT, standarkan, QC, agregasi mingguan.

Prasyarat: audit SiTMAT (jumlah stasiun, panjang deret waktu, format unduhan, lisensi).

Masuk : data/raw/ (ekspor SiTMAT)
Keluar: data/interim/stations.geojson, data/interim/stations_weekly.parquet
Kolom baku: station_id, lon, lat, khg_id, tipe_lahan, date, wtd_cm (negatif = di bawah permukaan)
Langkah:
  1. Baca dan samakan nama kolom, satuan (cm), dan datum.
  2. QC: rentang wajar, lompatan mendadak, duplikat, deret terlalu pendek.
  3. Agregasi mingguan (median) dan catat jumlah pengukuran per minggu.
"""
raise NotImplementedError("Tulis setelah format data SiTMAT diketahui.")
