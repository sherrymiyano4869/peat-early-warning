# WebGIS dan pembaruan otomatis

## Yang sudah ada
- `scripts/09_export_web.py` mengubah hasil menjadi aset statis di `webmap/data/`: hamparan PNG (dari GeoTIFF grid), `stations.geojson`,
  deret waktu per stasiun, dan `manifest.json` (versi, data sampai kapan, tanggal terbit, status validasi, legenda, atribusi, penafian).
- `webmap/index.html` + `app.js` (Leaflet) membaca aset itu. Uji lokal: `python -m http.server -d webmap 8000`, buka http://localhost:8000.
- Hosting: apa pun yang menyajikan berkas statis (GitHub Pages, Netlify, server berkas kampus). Tidak perlu basis data atau server aplikasi.

## Alur pembaruan yang diusulkan
| Frekuensi | Langkah |
|---|---|
| Harian atau tiap beberapa hari | potret SiTMAT (`01a`), detail stasiun (`01b`), ekstraksi fitur hanya untuk tanggal baru |
| Mingguan | `03_assemble` -> latih ulang dan `06_predict` (+ `--walk-forward`) -> `09_export_web` -> publikasi |
Jendela data SiTMAT hanya sekitar 30 hari, jadi potret tidak boleh terlewat lebih dari sekitar 2 minggu.

## Kebijakan pelatihan ulang LightGBM
- Latih ulang penuh tiap minggu dengan semua data yang sudah terkumpul (data kecil, hitungan detik sampai menit). Tidak perlu pembelajaran daring.
- Gerbang validasi: model baru dipublikasikan hanya bila hasil walk-forward terbaru tidak lebih buruk daripada ambang (skill dan cakupan q10-q90).
  Bila gagal, peta tetap memakai model sebelumnya dan menampilkan "data sampai" yang jujur.
- Simpan tiap model beserta jendela data latih, fitur, dan metriknya agar hasil bisa diulang.
- Kelas kepercayaan peta otomatis mengikuti skill walk-forward terbaru (src/confidence.py).

## Yang belum dibangun (butuh pekerjaan sebelum otomatis penuh)
1. Mode inkremental di `02_gee_features.py` (`--since`): kini berkas yang ada dilewati, belum ditambah per tanggal baru.
2. Orkestrator `run_update.py` (urutan langkah, log, berhenti bila satu langkah gagal) dan registri model dengan gerbang validasi.
3. Autentikasi Earth Engine tanpa interaksi (service account) dan pemeriksaan kuota nonkomersial.
4. Penjadwal: GitHub Actions (cron), cron di server kecil, atau Windows Task Scheduler (WSL tidak selalu menyala).
5. Pemantauan: peringatan bila potret gagal atau data berhenti, dan tampilan "data sampai" di peta (sudah ada di manifest).
6. Model peta per sel dan lapisan risiko dan kepercayaan (`08`); `09` otomatis menyertakan `risk.tif` dan `confidence_class.tif` bila ada.

## Ketentuan
Cantumkan atribusi (OpenStreetMap, FABDEM, SiTMAT/KLH/BRGM, JAXA GSMaP, Copernicus) di peta (sudah di manifest). FABDEM CC BY-NC-SA 4.0:
turunan yang dibagikan ikut berlisensi sama. Periksa ketentuan situs SiTMAT sebelum mempublikasikan ulang nilai muka air.
