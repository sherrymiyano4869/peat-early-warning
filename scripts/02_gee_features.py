"""02_gee_features: ekstraksi fitur dari Earth Engine untuk stasiun-minggu.

Masuk : data/interim/stations.geojson
Keluar: data/features/gee_features.parquet
Urutan dari yang termurah:
  a. Statis: elevasi dan kemiringan (COPERNICUS/DEM/GLO30).
  b. Hujan: UCSB-CHG/CHIRPS/DAILY -> jumlah 7/14/30 hari sebelum tiap minggu.
  c. Sentinel-1 (COPERNICUS/S1_GRD): median VV dan VH 10 harian.
  d. Sentinel-2: NDMI dan NDWI 10 harian dengan masking awan (Cloud Score+).
  e. ERA5-Land: suhu dan evaporasi harian (ECMWF/ERA5_LAND/DAILY_AGGR).
Gunakan reduceRegions di server, proses per tahun, simpan hasil per tahun,
dan ukur pemakaian EECU sebelum menjalankan penuh.
"""
raise NotImplementedError("Tulis setelah 01_stations menghasilkan stations.geojson.")
