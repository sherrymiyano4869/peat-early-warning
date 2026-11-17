# Pembaruan terbaru

Ringkasan untuk anggota tim, yang terbaru di atas. Catatan teknis lengkap per versi ada di [CHANGELOG.md](CHANGELOG.md).

## v0.22: API data (17 November 2026)

Ditambahkan **lapisan akses data (API)** di atas hasil pipeline yang sama. Isi data, model, dan tampilan web **tidak berubah**.
Halaman web belum memakai API; ia masih membaca `manifest.json` dan `response.json` seperti sebelumnya.

| | Sebelum (v0.21) | Sesudah (v0.22) |
|---|---|---|
| Cara data diakses | Browser membaca berkas JSON mentah (`manifest.json`, `response.json`, dan lainnya) | Ditambah alamat per sumber daya: `/v1/collections/stations/items`, `/fire-cells/items`, `/dryness-cells/items`, `/hotspots/items`, `/events/items`, dan lainnya (8 koleksi) |
| Ambil sebagian saja | Tidak bisa, berkas dibaca utuh | Bisa disaring: `bbox`, `datetime`, `days`, `limit`, `offset` |
| Pemakai luar (Postman, skrip, Python) | Harus tahu nama dan struktur berkas | Ada dokumentasi [docs/API.md](docs/API.md), skema [docs/api/openapi.json](docs/api/openapi.json), dan halaman `/docs` otomatis |
| Format galat | Tidak ada | Seragam: `{code, description}` |
| Menulis data | Tidak ada | Satu-satunya: PATCH status lapangan sebuah tugas pemeriksaan, hanya aktif bila `PEAT_API_TOKEN` disetel |
| Tanpa server | Web statis | Tetap bisa: `scripts/21_export_api.py` membuat cerminan statis di `webmap/data/v1` dengan bentuk yang sama |
| GeoJSON model 14 dan 15 | Tanpa id sel | Memuat `id` dan `cell_id` (angkanya sama) |

Catatan: ini **bukan CRUD penuh**. Semua sumber daya hanya bisa dibaca (GET). Satu-satunya tulis adalah PATCH status tugas,
yang disimpan tambah-saja (riwayat tidak bisa diubah atau dihapus) dan tidak memengaruhi hasil kejadian, yang tetap berasal dari laporan Kobo.

### Mencoba

    conda activate peat
    pip install fastapi uvicorn httpx        # sekali saja; juga tercatat di environment.yml
    uvicorn api.app:create_app --factory --port 8001

Lalu buka `http://localhost:8001/docs` (dokumentasi interaktif). Untuk Postman: Import, lalu tempel `http://localhost:8001/openapi.json`
(atau pilih berkas `docs/api/openapi.json`). Contoh alamat:

- `/v1/collections` : daftar koleksi dan penyaring yang sah
- `/v1/collections/stations/items?limit=2`
- `/v1/collections/dryness-cells/items?bbox=103.6,-1.4,103.8,-1.2&limit=1`
- `/v1/collections/hotspots/items?days=7`
- `/v1/validation` dan `/v1/scores`

Mengaktifkan PATCH (hanya bila memang perlu): `export PEAT_API_TOKEN=$(openssl rand -hex 24)` sebelum menjalankan server.
Token jangan ditulis ke berkas repo dan jangan ditempel ke obrolan. Rincian lengkap: [docs/API.md](docs/API.md).

### Belum teruji
- PATCH dengan token (hanya jalur tanpa token yang sudah dicoba) dan mode cerminan statis `webmap/data/v1`.
- Penyaring `bbox` sudah dicoba pada sel pengeringan; `datetime` belum dicoba terhadap data asli.
- Server tidak boleh dibuka ke jaringan luar tanpa HTTPS bila PATCH diaktifkan.

## Skrip pembaruan data penuh (`update_data.sh`)

Satu skrip untuk memperbarui data dari sumber luar sampai webmap: hujan dan kelembapan tanah (Earth Engine), NDMI, titik api FIRMS,
fitur dinamis, model dan peta, lalu laporan Kobo dan halaman Respons. Berhenti di galat pertama; log di `outputs/logs/`.

    export FIRMS_MAP_KEY=...  KOBO_TOKEN=...  KONTAK=emailmu@contoh.com
    ./update_data.sh [--tanpa-ndmi] [--tanpa-stasiun] [--label "teks"]

Kunci dan token jangan pernah disimpan di repo. Urutan langkah ada di komentar awal skrip.
