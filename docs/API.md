# Kontrak API v1

Satu sumber daya = satu jenis data, bukan satu tab dan bukan satu tombol. Satu sel atau satu stasiun adalah **item** di dalam sumber daya itu.
Pola alamat mengikuti OGC API – Features: `/collections/{id}/items` (daftar) dan `/collections/{id}/items/{featureId}` (satu item).
Kontrak ini diubah lebih dulu sebelum kode; skema mesin ada di `docs/api/openapi.json` (dibuat `scripts/21_export_api.py --openapi`).

## Menjalankan

```bash
uvicorn api.app:create_app --factory --port 8000                        # API /v1, dokumentasi /docs, web di /
PEAT_API_TOKEN=gantiini uvicorn api.app:create_app --factory --port 8000  # + PATCH tugas
python scripts/21_export_api.py --openapi docs/api/openapi.json          # cermin statis webmap/data/v1 + skema
```

Postman: Import → `http://localhost:8000/openapi.json` (atau berkas `docs/api/openapi.json`). Semua endpoint muncul sendiri.

## Aturan

1. Semua hasil pipeline **hanya GET**. Prediksi, indeks, VIIRS, buku besar, dan skor tidak bisa diubah lewat API; arsip prediksi harus tetap supaya penilaian prospektif (18) sah.
2. Satu-satunya tulis: `PATCH /v1/collections/tasks/items/{id}` untuk **status lapangan** tugas. Hasil kejadian (`hasil`) tetap hanya dari laporan KoboToolbox (16 → 17 → 20). PATCH tidak dibaca 17 atau 18.
3. Status tugas disimpan tambah-saja (`data/interim/task_updates.sqlite`); tidak ada DELETE. Koreksi = PATCH baru.
4. Koordinat lon/lat EPSG:4326, tanggal `YYYY-MM-DD` WIB, waktu ISO 8601 UTC (`...Z`). Id sel = `cell_id` grid induk 1 km (ESRI:54034), sebagai string.
5. Tidak ada titik laporan kejadian, kode pelapor, atau alasan tugas di respons mana pun.

## Sumber daya dan tab pemakainya

| Sumber daya | Monitoring | Prediksi | Respons | Id item | Penyaring selain `limit`, `offset`, `bbox` |
|---|:-:|:-:|:-:|---|---|
| `GET /v1/meta` | ✓ | ✓ | ✓ | – | – |
| `collections/stations` | ✓ | ✓ | | id stasiun | `region` |
| `GET /v1/stations/{id}/series?days=` | ✓ | ✓ | | – | `days` |
| `collections/hotspots` | ✓ | | | `tanggal_dn_lon_lat` | `datetime`, `days`, `dn`, `min_conf`, `min_frp` |
| `GET /v1/susceptibility` | ✓ | ✓ | | – | – |
| `GET /v1/layers` | ✓ | | | – | – |
| `collections/fire-cells` | | ✓ | ✓ | `cell_id` | `min_p1`, `min_p3`, `max_rank` |
| `collections/dryness-cells` | | ✓ | | `cell_id` | `min_p7`, `min_p14` |
| `GET /v1/validation` | | ✓ | | – | – |
| `collections/events` | | | ✓ | `cell_id_tanggal` | `datetime`, `days`, `sumber`, `status`, `tingkat` |
| `collections/tasks` | | | ✓ | `id_tugas` | `hasil`, `status_lapangan` |
| `collections/canal-blocks` | | | ✓ | `titik` | `datetime`, `days`, `kondisi` |
| `collections/field-water-levels` | | | ✓ | `titik` | `datetime`, `days` |
| `GET /v1/scores` | | | ✓ | – | – |

`fire-cells` dipakai dua tab tetapi satu endpoint; karena itu pembagian per tab akan menggandakan data.
`datetime`: `2026-11-01/2026-11-08`, `2026-11-01/..`, `../2026-11-08`, atau satu tanggal. `days=n`: n hari terakhir terhitung dari tanggal terakhir di koleksi itu.
Parameter yang tidak dikenal ditolak (400), supaya salah ketik tidak diam-diam mengembalikan semua data. Daftar sah per koleksi: `queryables` di `GET /v1/collections`.

## Alur tiap fitur (asal daftar endpoint)

| Fitur | Alur |
|---|---|
| Stasiun | lapisan hidup → `items` stasiun → klik → `stations/{id}/series?days=90` |
| Titik api teramati | lapisan hidup → `hotspots/items?days=7` |
| Kerawanan | lapisan hidup → `susceptibility` → tile dari `base_url` + `levels[].url` |
| Peluang titik api | tema dipilih → `fire-cells/items` → klik sel → `fire-cells/items/{cell_id}` |
| Pengeringan per sel | tema dipilih → `dryness-cells/items` → klik sel → `dryness-cells/items/{cell_id}` |
| Lencana bukti | halaman dibuka → `validation` |
| Kejadian | penggeser waktu → `events/items?datetime=a/b&sumber=...` |
| Tugas | lapisan hidup → `tasks/items` → petugas menandai → `PATCH tasks/items/{id}` → `.../history` |
| Sekat, muka air lapangan, skor | lapisan hidup → koleksinya; panel → `scores` |

## Bentuk respons

Daftar item (`application/geo+json`). Anggota tingkat koleksi seperti `issue_date` ikut di atas `features`:

```json
{"type": "FeatureCollection", "issue_date": "2026-11-10", "numberMatched": 120, "numberReturned": 2,
 "features": [{"type": "Feature", "id": "19971311569", "geometry": {"type": "Polygon", "coordinates": [[[103.9261, -1.3024], "..."]]},
               "properties": {"cell_id": "19971311569", "p7": 0.12, "p14": 0.31, "d7": -1.0, "d14": -2.0, "q10_14": -5.0, "q90_14": 1.0}}]}
```

PATCH tugas (header `Authorization: Bearer <token>`; kolom yang tidak dikirim tetap):

```json
{"status": "diperiksa", "dikunjungi_pada": "2026-11-11T10:00:00+07:00", "catatan": "akses lewat kanal"}
```

`status`: `belum`, `dalam_perjalanan`, `diperiksa`, `tidak_terjangkau`. `diperiksa` dan `tidak_terjangkau` wajib `dikunjungi_pada` dengan zona waktu,
tidak sebelum tanggal terbit tugas dan tidak di masa depan. `catatan` paling 280 karakter dan tanpa nama orang. Respons: item tugas terbaru dengan
`status_lapangan`, `dikunjungi_pada`, `diperbarui_pada`.

Galat selalu `{"code": "...", "description": "..."}`:

| HTTP | code | Arti |
|---|---|---|
| 400 | `parameter_tidak_sah` | penyaring, isi PATCH, atau aturan waktu salah |
| 401 | `tidak_berwenang` | token salah atau tidak ada |
| 403 | `tulis_nonaktif` | server tanpa `PEAT_API_TOKEN` |
| 404 | `tidak_ditemukan` | koleksi atau item tidak ada |
| 503 | `data_belum_ada` | berkas pipeline belum dibuat; pesan menyebut skripnya |

## Pemakai di webmap

`webmap/api.js` memanggil `v1/...` bila server berjalan, dan `data/v1/....json` bila tidak (alamat relatif, jadi jalan juga di sub-folder hosting).
Dipakai oleh `monitoring.html` (kartu tugas terbuka dari `collections/tasks/items`) dan `petugas.html` (daftar tugas dan PATCH).
Halaman lain masih membaca `manifest.json` dan `response.json` langsung.

## Mode statis (tanpa server)

`scripts/21_export_api.py` menulis respons yang sama ke `webmap/data/v1/…json` (alamat server + `.json`), misalnya
`data/v1/collections/fire-cells/items.json`. Mode ini tanpa penyaring, tanpa item tunggal, dan tanpa PATCH; status tugas yang ada di basis data
saat ekspor ikut tercetak. Kesamaannya dengan server diuji di `tests/test_api.py`.
