# Mengambil hasil formulir KoboToolbox (panduan untuk anggota tim)

Formulir laporan lapangan (`forms/laporan_lapangan.xlsx`) terpasang di akun KoboToolbox pemilik repo, di server
`https://kf.kobotoolbox.org`, dengan asset UID `aYFk7zwjP9nVTWSJAftCth`.

Ada dua keperluan yang berbeda. Pilih yang sesuai:

| Keperluan | Cara | Butuh repo ini? |
|---|---|---|
| Hanya mau berkas Excel/CSV berisi kiriman formulir | Cara A: unduh dari situs Kobo | Tidak |
| Mau laporan tampil di halaman Respons webmap di komputermu | Cara B: tarik dengan script 16 | Ya |

Jangan meminta atau memakai token API milik orang lain. Token itu membuka seluruh akun pemiliknya, bukan hanya formulir ini.

## Langkah 0 (sekali saja): minta akses

1. Buat akun di https://kf.kobotoolbox.org kalau belum punya.
2. Kirim **username** Kobo-mu ke pemilik formulir.
3. Pemilik formulir membuka proyeknya, lalu Settings → Sharing → Add user, memasukkan username-mu, dan mencentang
   **View submissions** (tambahkan Add submissions bila kamu juga akan mengisi formulir lewat akunmu).
4. Setelah itu proyeknya muncul di daftar proyek akunmu.

## Cara A: unduh dari situs Kobo

1. Masuk ke https://kf.kobotoolbox.org dan buka proyek formulirnya.
2. Buka tab **DATA**, lalu **Downloads**.
3. Pilih jenis ekspor (XLS atau CSV). Untuk "Value and header format" pilih **XML values and headers**, supaya nama kolom
   sama dengan yang dipakai script (`jenis`, `lokasi`, `waktu_amat`, dan seterusnya).
4. Klik **Export**, tunggu sampai muncul di daftar di bawahnya, lalu unduh.

Berkas ini memuat titik koordinat laporan. Simpan untuk tim saja.

## Cara B: tarik ke pipeline dan tampilkan di webmap

Prasyarat: repo sudah di-clone dan lingkungan `peat` sudah terpasang (lihat README, bagian "Pasang lingkungan").
Untuk halaman Respons kamu tidak perlu akun Earth Engine. Yang wajib ada adalah `data/interim/hotspots.parquet`
(titik api); cara termudah mendapatkannya adalah mengekstrak zip contoh data dari halaman Releases repo ini ke folder repo.

1. Ambil token API **akunmu sendiri**: di situs Kobo, klik ikon akun di kanan atas → Account Settings → Security → API Key.
2. Di terminal, dari folder repo:

       conda activate peat
       export PROJ_DATA=$(python -c "import pyproj;print(pyproj.datadir.get_data_dir())")
       export KOBO_TOKEN=tokenmu_di_sini

   Tanpa spasi di sekitar `=`. Token jangan ditulis ke berkas mana pun di repo dan jangan ditempel ke obrolan.

3. Tarik laporan dan bangun ulang halaman Respons:

       python scripts/16_ingest_reports.py --kobo-asset aYFk7zwjP9nVTWSJAftCth \
        && python scripts/17_event_ledger.py \
        && python scripts/18_score_prospective.py \
        && python scripts/20_export_response.py

4. Buka webmap:

       python -m http.server -d webmap 8000

   lalu buka http://localhost:8000/response.html (harus lewat localhost, bukan klik ganda berkas html).

Ulangi langkah 3 setiap ada kiriman baru, lalu muat ulang halaman dengan Ctrl+F5.

### Yang dihasilkan
- `data/raw/laporan/kobo/<waktu>.json.gz`: potret mentah tiap tarikan. Identitas akun dan perangkat pengirim sudah dibuang; titik koordinat tetap ada.
- `data/interim/reports.parquet`: satu baris per laporan sah, sudah dipetakan ke sel 1 km. Ini berkas yang paling enak dibuka untuk analisis.
- `webmap/data/response.json`: data halaman Respons. Hanya sel 1 km, tanpa titik laporan dan tanpa kode pelapor.

Semua folder itu diabaikan git, jadi tidak ikut ter-commit.

### Kalau hasilnya tidak sesuai harapan
- **"KOBO_TOKEN belum diset"**: baris `export KOBO_TOKEN=...` belum dijalankan di terminal yang sama, atau nilainya kosong.
- **Galat 401 atau 403**: token salah. **Galat 404**: formulir belum dibagikan ke akunmu (ulangi Langkah 0) atau UID salah.
- **Jumlah laporan tidak bertambah**: kiriman belum sampai ke server Kobo. Di KoboCollect, periksa apakah masih di daftar "siap dikirim".
- **Laporan tidak terlihat di peta**: halaman Respons bawaannya menampilkan 14 hari terakhir. Ubah "Panjang rentang" menjadi "semua",
  lalu perbesar peta; tiap laporan digambar sebagai sel 1 km sehingga kecil saat peta diperkecil.
- **Laporan ditandai "terlambat"**: dikirim lebih dari 3 hari setelah waktu pengamatan yang diisi. Laporan tetap dipakai,
  tetapi tampil sebagai "belum terverifikasi (tingkat C)".

## Catatan kejujuran
- Cara B sudah dijalankan terhadap server Kobo sungguhan oleh pemilik formulir (12 November 2026, 5 laporan uji).
  Yang **belum diuji** adalah menariknya dari akun kedua yang hanya diberi izin View submissions.
- Script 16 juga menerima berkas lewat `--csv berkas.csv --source NAMA`, tetapi itu baru diuji dengan CSV buatan
  `tools/fake_reports.py`, belum dengan berkas ekspor dari situs Kobo (pemisah kolom dan nama kolomnya bisa berbeda).
  Untuk pipeline, pakai Cara B.
