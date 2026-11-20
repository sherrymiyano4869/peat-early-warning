/* i18n-en.js: kamus Indonesia -> Inggris. Kunci = teks Indonesia persis (spasi dinormalkan); pola untuk teks bervariabel di I18N_EN_RX. Lihat docs/I18N.md. Berkas lokal, bukan dari zip web. */
window.I18N_EN_RX = [
[
"Versi (\\S+) · dibuat (\\S+) · data sampai (\\S+) · tanggal terbit prediksi (\\S+)",
"Version {1} · generated {2} · data up to {3} · forecasts issued {4}"
],
[
"Versi (\\S+) · dibuat (\\S+)",
"Version {1} · generated {2}"
],
[
"Buku besar (.+) s/d (.+)",
"Ledger {1:d} to {2:d}"
],
[
"([\\d.]+) titik api VIIRS dalam 7 hari terakhir \\(sampai (.+?)\\)\\. Muka air di (\\d+) dari (\\d+) stasiun SiTMAT berada di bawah −40 cm pada pembacaan terakhir\\.",
"{1:n} VIIRS hotspots in the last 7 days (up to {2:d}). The water table at {3} of {4} SiTMAT stations was below −40 cm at the latest reading."
],
[
"([\\d.]+) titik api VIIRS dalam 7 hari terakhir \\(sampai (.+?)\\)\\.",
"{1:n} VIIRS hotspots in the last 7 days (up to {2:d})."
],
[
"Muka air di (\\d+) dari (\\d+) stasiun SiTMAT berada di bawah −40 cm pada pembacaan terakhir\\.",
"The water table at {1} of {2} SiTMAT stations was below −40 cm at the latest reading."
],
[
"(\\d+) kelas dari batas tetap \\(kuintil teoretis rata-rata dua peringkat terhadap riwayat: (.+)\\); kelas relatif, bukan ambang absolut",
"{1} classes from fixed breaks (theoretical quintiles of the mean of two ranks against history: {2}); relative classes, not absolute thresholds"
],
[
"Uji retrospektif \\((\\S+) s/d (\\S+), bulan api\\): PR-AUC model (\\S+) lawan klimatologi (\\S+) dan persistensi (\\S+); skill Brier (\\S+)\\. Belum diuji prospektif pada arsip\\. Kepercayaan: (\\w+)\\.",
"Retrospective test ({1} to {2}, fire months): model PR-AUC {3:n} vs climatology {4:n} and persistence {5:n}; Brier skill {6:n}. Not yet tested prospectively on the archive. Confidence: {7:t}."
],
[
"Model titik api belum terbukti mengalahkan klimatologi dan persistensi pada uji \\(PR-AUC (\\S+) lawan (\\S+) dan (\\S+)\\)\\. Kepercayaan: (\\w+)\\.",
"The hotspot model has not yet been shown to beat climatology and persistence in testing (PR-AUC {1:n} vs {2:n} and {3:n}). Confidence: {4:t}."
],
[
"Uji retrospektif (\\S+) s/d (\\S+); skill Brier (\\S+)\\. Belum diuji prospektif pada arsip\\.",
"Retrospective test {1} to {2}; Brier skill {3:n}. Not yet tested prospectively on the archive."
],
[
"Uji retrospektif titik api: (\\S+) s/d (\\S+)",
"Retrospective hotspot test: {1} to {2}"
],
[
"Model belum terbukti lebih baik daripada persistensi \\(skill (\\S+)\\)\\. Kepercayaan: (\\w+)\\. Rentang q10–q90 mencakup (\\S+) kenyataan \\(target 80%\\)\\.",
"The model has not yet been shown to beat persistence (skill {1:n}). Confidence: {2:t}. The q10–q90 range covers {3:n} of outcomes (target 80%)."
],
[
"Model belum terbukti lebih baik daripada persistensi \\(skill (\\S+)\\)\\. Kepercayaan: (\\w+)\\.",
"The model has not yet been shown to beat persistence (skill {1:n}). Confidence: {2:t}."
],
[
"Prakiraan muka air stasiun: (.+)",
"Station water-table forecast: {1:t}"
],
[
"Skill kecil terhadap persistensi \\((\\S+)\\)\\. Kepercayaan: (\\w+)\\.(?: Rentang q10–q90 mencakup (\\S+) kenyataan \\(target 80%\\)\\.)?",
"Small skill against persistence ({1:n}). Confidence: {2:t}."
],
[
"Pengeringan per sel belum terbukti pada stasiun baru dan tanggal baru \\(skill MAE (\\S+), cakupan q10–q90 (\\S+), (\\d+) stasiun\\)\\. Kepercayaan: (\\w+)\\.",
"Per-cell drying is not yet proven at new stations and new dates (MAE skill {1:n}, q10–q90 coverage {2:n}, {3} stations). Confidence: {4:t}."
],
[
"Uji ruang-waktu \\((\\d+) stasiun\\): skill MAE (\\S+) lawan \\\"tetap\\\", cakupan q10–q90 (\\S+)\\. Belum diuji di luar klaster stasiun\\. Kepercayaan: (\\w+)\\.",
"Space-time test ({1} stations): MAE skill {2:n} vs \"unchanged\", q10–q90 coverage {3:n}. Not tested outside the station clusters. Confidence: {4:t}."
],
[
"Pengeringan: uji ruang-waktu pada (\\d+) stasiun",
"Drying: space-time test at {1} stations"
],
[
"(\\d+) hari: skill MAE (\\S+) lawan \\\"tetap\\\"; cakupan q10–q90 (\\S+) \\(target 80%\\); (\\S+) uji",
"{1} days: MAE skill {2:n} vs \"unchanged\"; q10–q90 coverage {3:n} (target 80%); {4:n} tests"
],
[
"Prediksi diarsipkan sebelum kejadian, lalu dinilai: lolos uji prospektif (ya|belum)",
"Forecasts are archived before events, then scored: passed the prospective test: {1:t}"
],
[
"Data sampai (.+)",
"Data up to {1:d}"
],
[
"([\\d.]+) hari ini",
"{1:n} today"
],
[
"dari ([\\d.]+) sel · kepercayaan (\\w+)",
"of {1:n} cells · {2:t} confidence"
],
[
"([+−-]?\\d+) dibanding 7 hari lalu",
"{1} vs 7 days ago"
],
[
"dari (\\d+) tugas",
"of {1} tasks"
],
[
"(\\d+) tanpa data",
"{1} no data"
],
[
"Semua stasiun \\((\\d+)\\)",
"All stations ({1})"
],
[
"(\\d+)\\. Sel (\\d+)",
"{1}. Cell {2}"
],
[
"3 hari: (.+) · rata-rata bulan ini (.+)",
"3 days: {1:n} · this month's average {2:n}"
],
[
"7 hari: (.+) · median 14 hari (.+) cm",
"7 days: {1:n} · 14-day median {2:n} cm"
],
[
"Median (\\d+) stasiun SiTMAT di area pilot; negatif = di bawah permukaan tanah\\. Data stasiun baru ada sejak (\\S+)\\.",
"Median of {1} SiTMAT stations in the pilot area; negative = below the ground surface. Station data only start on {2}."
],
[
"Ringkasan (.+), bukan nilai per sel\\. Arahkan kursor ke grafik untuk membaca nilai\\.",
"Summary {1:t}, not per-cell values. Hover over a chart to read values."
],
[
"normal (\\d{4}–\\d{4})",
"normal {1}"
],
[
"\\(normal ([^)]+)\\) · (.+)",
"(normal {1:n}) · {2:d}"
],
[
"· (\\d{1,2} \\S+ \\d{4})",
"· {1:d}"
],
[
"tidak ada nilai di (.+)",
"no value on {1:d}"
],
[
"([−-]?[\\d.,]+) hari",
"{1:n} days"
],
[
"([\\d.,]+) titik",
"{1:n} hotspots"
],
[
"([−-]?[\\d.,]+) indeks",
"{1:n} index"
],
[
"(.+) · (sumatra|kalimantan|papua)",
"{1} · {2:t}"
],
[
"· (\\d+) stasiun",
"· {1} stations"
],
[
"· ([\\d.]+) titik, sampai (\\S+)",
"· {1:n} hotspots, up to {2}"
],
[
"· ([\\d.]+) sel; kepercayaan (\\w+)",
"· {1:n} cells; {2:t} confidence"
],
[
"Tingkat tampilan peta kerentanan pada zoom ini: (.+)\\.",
"Susceptibility map display level at this zoom: {1:t}."
],
[
"Hanya (\\S+) sel teratas menurut peluang besok yang digambar, juga untuk horizon 3 hari\\.",
"Only the top {1:n} of cells by tomorrow's probability are drawn, also for the 3-day horizon."
],
[
"Hanya sel teratas menurut peluang besok yang digambar, juga untuk horizon 3 hari\\.",
"Only the top cells by tomorrow's probability are drawn, also for the 3-day horizon."
],
[
"Hanya (\\S+) sel teratas yang digambar\\. Peluang dikalibrasi; harapan jumlah sel berapi besok (\\S+) dari (\\S+) sel\\.",
"Only the top {1:n} of cells are drawn. Probabilities are calibrated; expected number of cells with fire tomorrow: {2:n} of {3:n}."
],
[
"dari ([\\d.]+)",
"of {1:n}"
],
[
"per sel \\(([\\d.]+) sel\\)",
"per cell ({1:n} cells)"
],
[
"peringkat (\\d+) dari (\\d+) sel teratas · terbit (.+)",
"rank {1} of {2} top cells · issued {3:d}"
],
[
"prakiraan pengeringan · terbit (.+)",
"drying forecast · issued {1:d}"
],
[
"rata-rata sel ini bulan ini (\\S+)",
"this cell's average this month {1:n}"
],
[
"\\(rata-rata sel ini pada bulan ini (\\S+)\\)",
"(this cell's average this month {1:n})"
],
[
"\\(rata-rata (\\S+)\\)",
"(average {1:n})"
],
[
"rata-rata (\\S+)",
"average {1:n}"
],
[
"median (\\S+) cm \\(rentang (\\S+) s/d (\\S+)\\)",
"median {1:n} cm (range {2:n} to {3:n})"
],
[
"median (\\S+) cm",
"median {1:n} cm"
],
[
"(\\w+) \\(dari uji model, bukan per sel\\)",
"{1:t} (from the model test, not per cell)"
],
[
"PR-AUC (\\S+)",
"PR-AUC {1:n}"
],
[
"(\\d+) (\\S+) \\((\\d+) dari (\\d+)\\)",
"{1} {2:n} ({3} of {4})"
],
[
"Bagian sel yang kejadiannya ditemukan saat diperiksa \\(skrip 18\\)\\. Jumlah kecil: baca sebagai petunjuk\\.(.*)",
"Share of checked cells where an event was found (script 18). Small numbers: read as a hint.{1:t}"
],
[
"(\\d+) tugas, (\\d+) sudah diperiksa \\((\\d+) ada kejadian, (\\d+) nihil\\)",
"{1} tasks, {2} checked ({3} with an event, {4} nothing found)"
],
[
"(\\d+) tugas, (\\d+) sudah diperiksa",
"{1} tasks, {2} checked"
],
[
"\\((\\d+) ada kejadian, (\\d+) nihil\\)",
"({1} with an event, {2} nothing found)"
],
[
"Terbit (.+) · sel (\\d+)",
"Issued {1:d} · cell {2}"
],
[
"Terbit (.+)",
"Issued {1:d}"
],
[
"terbit (.+)",
"issued {1:d}"
],
[
"Tugas (T\\d{8}-\\d{3})",
"Task {1}"
],
[
"Sel (\\d+)",
"Cell {1}"
],
[
"Sel (\\d+) · (.+)",
"Cell {1} · {2:d}"
],
[
"(\\d+) terbuka",
"{1} open"
],
[
"Status sel (\\d+)",
"Status of cell {1}"
],
[
"kunjungan (.+)",
"visit {1}"
],
[
"Titik muka air (.+)",
"Water-level point {1}"
],
[
"Bacaan terakhir \\((.+)\\):",
"Latest reading ({1:d}):"
],
[
"(\\d+) laporan",
"{1} report(s)"
],
[
"(\\d+) bacaan",
"{1} reading(s)"
],
[
"\\((\\d{1,2} \\S+ \\d{4})\\)",
"({1:d})"
],
[
"Sekat (.+)",
"Block {1}"
],
[
"(\\d{1,2} \\S+ \\d{4}): (.+)",
"{1:d}: {2:p}"
],
[
"VIIRS (\\d+) deteksi",
"VIIRS {1} detections"
],
[
"(\\d+) laporan (membara|api|asap) \\(tingkat (\\w), cocok dengan satelit\\)",
"{1} {2:t} report(s) (level {3}, matches satellite)"
],
[
"(\\d+) laporan (membara|api|asap) \\(tingkat (\\w)\\)",
"{1} {2:t} report(s) (level {3})"
],
[
"(\\d+) laporan nihil \\(tingkat (\\w)\\)",
"{1} nothing-found report(s) (level {2})"
],
[
"(\\d+) laporan nihil",
"{1} nothing-found report(s)"
],
[
"Laporan lapangan dikumpulkan lewat KoboToolbox; identitas pelapor tidak disimpan dan titik laporan hanya ditampilkan per sel 1 km\\. Titik api: VIIRS 375 m \\(NASA FIRMS\\)\\. Satelit tidak dipakai sebagai bukti nihil karena awan, asap, dan api membara lolos dari deteksi\\. Laporan dianggap cocok dengan satelit bila berjarak ≤ (\\S+) m dan ≤ (\\S+) jam \\(angka awal\\)\\.",
"Field reports are collected through KoboToolbox; reporter identities are not stored and report points are only shown per 1 km cell. Hotspots: VIIRS 375 m (NASA FIRMS). Satellites are not used as evidence of no fire because clouds, smoke, and smouldering fires escape detection. A report counts as matching the satellite when it is within {1:n} m and {2:n} hours (initial values)."
],
[
"Laporan lapangan dikumpulkan lewat KoboToolbox; identitas pelapor tidak disimpan dan titik laporan hanya ditampilkan per sel 1 km\\. Titik api: VIIRS 375 m \\(NASA FIRMS\\)\\. Satelit tidak dipakai sebagai bukti nihil karena awan, asap, dan api membara lolos dari deteksi\\.",
"Field reports are collected through KoboToolbox; reporter identities are not stored and report points are only shown per 1 km cell. Hotspots: VIIRS 375 m (NASA FIRMS). Satellites are not used as evidence of no fire because clouds, smoke, and smouldering fires escape detection."
],
[
"Muka air terakhir \\((.+)\\):",
"Latest water table ({1}):"
],
[
"(turun|naik) ([\\d.,]+) cm dalam 7 hari terakhir",
"{1:t} {2:n} cm over the last 7 days"
],
[
"muka air harian, (\\S+) s/d (\\S+)",
"daily water table, {1} to {2}"
],
[
"(\\d+) hari ke depan:",
"Next {1} days:"
],
[
"(tetap|turun|naik) ([\\d.,]+) cm \\(rentang (\\S+) s/d (\\S+)\\); peluang turun ≥ 10 cm (\\S+)",
"{1:t} {2:n} cm (range {3:n} to {4:n}); probability of a ≥ 10 cm drop {5:n}"
],
[
"\\(rata-rata di data latih (\\S+)\\)",
"(training-data average {1:n})"
],
[
"Tanggal \\(WIB\\): (\\S+) · (malam|siang)",
"Date (WIB): {1} · {2:t}"
],
[
"Keyakinan deteksi: (\\w+) · FRP: (\\S+) MW",
"Detection confidence: {1:t} · FRP: {2:n} MW"
],
[
"\\(indeks rata-rata (\\S+)\\)",
"(mean index {1:n})"
],
[
"Bagian sel kelas tinggi atau sangat tinggi: (\\S+)",
"Share of cells in the high or very high class: {1:n}"
],
[
"Cakupan data: (\\S+) · kepercayaan rendah: (\\S+)",
"Data coverage: {1:n} · low confidence: {2:n}"
],
[
"Sel 1 km · peringkat (\\d+)",
"1 km cell · rank {1}"
],
[
"(\\d{1,2} \\S+ \\d{4}) – (\\d{1,2} \\S+ \\d{4})",
"{1:d} – {2:d}"
],
[
"(\\d{1,2} (?:Jan|Feb|Mar|Apr|Mei|Jun|Jul|Agu|Sep|Okt|Nov|Des) \\d{4})",
"{1:d}"
],
[
"· (.+)",
"· {1:t}"
],
[
"([−+-]?\\d{1,3}(?:\\.\\d{3})*(?:,\\d+)?|[−+-]?\\d+,\\d+)( ?(?:%|cm|mm|MW|m³/m³|km|m))?",
"{1:n}{2}"
]
];
window.I18N_EN = {
 "Platform geospasial berbasis AI untuk memantau, memprediksi, dan merespons kebakaran gambut dengan lebih cepat, lebih tepat, dan lebih efektif": "AI-powered geospatial platform to monitor, predict, and respond to peatland fires faster, more precisely, and more effectively",
 "Menu utama": "Main menu",
 "Beranda": "Home",
 "Monitoring": "Monitoring",
 "Prediksi": "Prediction",
 "Respons": "Response",
 "Petugas": "Field officers",
 "Tentang": "About",
 "Tim": "Team",
 "Lapor": "Report",
 "Beranda · GEOFLAME (prototipe)": "Home · GEOFLAME (prototype)",
 "Tentang · GEOFLAME (prototipe)": "About · GEOFLAME (prototype)",
 "Tim · GEOFLAME (prototipe)": "Team · GEOFLAME (prototype)",
 "Lapor · GEOFLAME (prototipe)": "Report · GEOFLAME (prototype)",
 "Prakiraan peluang titik api dan pengeringan gambut tropis per sel 1 km, dibuat oleh mahasiswa magister Universitas Gadjah Mada.": "Hotspot-probability and drying forecasts for tropical peatlands per 1 km cell, built by master's students at Universitas Gadjah Mada.",
 "HALAMAN": "PAGES",
 "SUMBER DATA": "DATA SOURCES",
 "KONTAK": "CONTACT",
 "NASA FIRMS (titik api VIIRS)": "NASA FIRMS (VIIRS hotspots)",
 "Stasiun muka air SiTMAT": "SiTMAT water-table stations",
 "Sentinel-2 (NDMI) lewat Google Earth Engine": "Sentinel-2 (NDMI) via Google Earth Engine",
 "FABDEM dan ESA WorldCover": "FABDEM and ESA WorldCover",
 "Indeks ENSO dan IOD": "ENSO and IOD indices",
 "© 2026 Tim GEOFLAME": "© 2026 GEOFLAME team",
 "Prototipe riset · bukan peringatan resmi. Dalam keadaan darurat, hubungi BPBD setempat.": "Research prototype · not an official warning. In an emergency, contact your local BPBD.",
 "PERINGATAN DINI UNTUK GAMBUT TROPIS": "EARLY WARNING FOR TROPICAL PEATLANDS",
 "Peringatan dini kekeringan dan kebakaran gambut": "Early warning for peatland drought and fire",
 "Peluang titik api dan pengeringan muka air untuk setiap sel 1 km gambut Jambi, diterjemahkan menjadi tugas pemeriksaan bagi petugas lapangan. Prototipe riset, bukan peringatan resmi.": "Hotspot probability and water-table drying for every 1 km peatland cell in Jambi, turned into inspection tasks for field officers. Research prototype, not an official warning.",
 "Buka Monitoring": "Open Monitoring",
 "Cara kerja": "How it works",
 "Resolusi grid prakiraan": "Forecast grid resolution",
 "1–14 hari": "1–14 days",
 "Titik api 1–3 hari, muka air 7–14 hari": "Hotspots 1–3 days, water table 7–14 days",
 "Sumber data utama": "Main data sources",
 "Diarsipkan": "Archived",
 "Prediksi disimpan sebelum kejadian, lalu dinilai": "Forecasts are saved before events, then scored",
 "Satu sistem, untuk perencana dan petugas": "One system, for planners and field officers",
 "Dari meja perencana sampai lapangan, semua melihat prakiraan yang sama dalam bentuk yang mereka butuhkan.": "From the planner's desk to the field, everyone sees the same forecast in the form they need.",
 "PREDIKSI": "PREDICTION",
 "Ketahui di mana risiko naik": "Know where risk is rising",
 "Peluang titik api dan penurunan muka air untuk tiap sel 1 km, lengkap dengan status bukti dan tingkat kepercayaan model.": "Hotspot probability and water-table drop for each 1 km cell, with evidence status and model confidence level.",
 "Lihat prediksi →": "View predictions →",
 "RESPONS · PONSEL": "RESPONSE · MOBILE",
 "Kirim tim ke tempat yang penting": "Send teams where it matters",
 "Sel prioritas dan sampel acak menjadi tugas pemeriksaan dengan navigasi dan pencatatan status kunjungan.": "Priority cells and random samples become inspection tasks, with navigation and visit status logging.",
 "Lihat halaman petugas →": "View the field officer page →",
 "INFORMASI · SEGERA": "INFORM · COMING SOON",
 "Siapkan warga": "Keep communities ready",
 "Status sederhana per desa, prakiraan 7 hari, dan satu ketukan untuk melapor asap atau api. Halaman ini belum tersedia.": "A simple status per village, a 7-day outlook, and a one-tap way to report smoke or fire. This page is not available yet.",
 "Segera hadir": "Coming soon",
 "Dari piksel satelit sampai ke pintu yang tepat": "From satellite pixels to the right doorstep",
 "Kumpulkan": "Collect",
 "Titik api VIIRS, hujan, kelembapan tanah, NDMI, dan muka air stasiun SiTMAT.": "VIIRS hotspots, rainfall, soil moisture, NDMI, and SiTMAT station water levels.",
 "Model memberi skor peluang titik api dan penurunan muka air untuk setiap sel 1 km.": "The model scores hotspot probability and water-table drop for every 1 km cell.",
 "Periksa": "Inspect",
 "Sel berpeluang tertinggi, ditambah sampel acak, menjadi tugas pemeriksaan lapangan.": "The highest-probability cells, plus random samples, become field inspection tasks.",
 "Nilai": "Score",
 "Prediksi yang sudah diarsipkan dinilai terhadap laporan lapangan dan satelit sesudahnya.": "Archived forecasts are scored against the field reports and satellite observations that follow.",
 "DALAM PRAKTIK": "IN PRACTICE",
 "Peta peluang untuk setiap sel 1 km": "A probability map for every 1 km cell",
 "Model memberi skor setiap sel gambut, memeringkat sel yang sebaiknya diperiksa lebih dulu, dan menampilkan tingkat kepercayaannya.": "The model scores every peat cell, ranks the cells that should be checked first, and shows its confidence level.",
 "Peluang titik api besok dan 3 hari ke depan": "Hotspot probability for tomorrow and the next 3 days",
 "Prakiraan penurunan muka air 7 dan 14 hari": "Water-table drop forecasts for 7 and 14 days",
 "Status bukti dan kepercayaan ditampilkan untuk setiap model": "Evidence status and confidence are shown for every model",
 "Diuji retrospektif; penilaian prospektif memakai arsip prediksi": "Tested retrospectively; prospective scoring uses the forecast archive",
 "Jelajahi prediksi": "Explore predictions",
 "Ilustrasi grid sel dengan peluang titik api, bukan data nyata": "Illustration of a cell grid with hotspot probability, not real data",
 "Rendah": "Low",
 "Peluang titik api tinggi": "High hotspot probability",
 "Ilustrasi tampilan, bukan data nyata.": "Illustration only, not real data.",
 "Bawa peringatan dini ke wilayahmu": "Bring early warning to your region",
 "Kami mencari pemerintah daerah, BPBD, dan mitra masyarakat untuk menguji dan memvalidasi sistem ini di lapangan.": "We are looking for local governments, BPBD (disaster agencies), and community partners to test and validate this system in the field.",
 "Lihat prediksi": "View predictions",
 "TENTANG PROYEK": "ABOUT THE PROJECT",
 "Melihat Kebakaran Gambut Sebelum Dimulai": "Seeing Peat Fires Before They Start",
 "Sistem peringatan dini yang memadukan data satelit, pemantauan air tanah, dan pembelajaran mesin untuk menandai bagian gambut tropis yang mengering dan berpotensi terbakar.": "An early warning system that combines satellite data, groundwater monitoring, and machine learning to flag where tropical peatland is drying out and likely to burn.",
 "Tantangan Gambut Indonesia": "Indonesia's Peatland Challenge",
 "Indonesia menyimpan salah satu cadangan karbon gambut tropis terbesar di dunia. Ketika gambut yang terkeringkan mengering, ia menjadi bahan bakar kebakaran yang sulit dipadamkan dan menyelimuti wilayah dengan kabut asap.": "Indonesia holds one of the largest tropical peat carbon stores in the world. When drained peat dries out, it becomes fuel for fires that are hard to put out and cover the region in haze.",
 "Masalah kebakaran": "The fire problem",
 "Kebakaran gambut membara di bawah tanah, melepaskan banyak karbon, dan menimbulkan kabut asap yang merugikan kesehatan, sekolah, dan ekonomi.": "Peat fires smoulder underground, release large amounts of carbon, and cause haze that harms health, schools, and the economy.",
 "Saat titik api terlihat oleh satelit, kebakaran sering kali sudah sulit dikendalikan.": "By the time a hotspot shows up on satellite, the fire is often already hard to control.",
 "Celah pemantauan": "The monitoring gap",
 "Muka air tanah adalah sinyal terbaik untuk kekeringan gambut, tetapi stasiun pemantauan jarang dan berjauhan.": "Water-table level is the best signal of peat dryness, but monitoring stations are sparse and far apart.",
 "Tim lapangan punya waktu terbatas dan perlu tahu bagian mana dari ribuan hektare yang harus diperiksa lebih dulu.": "Field teams have limited time and need to know which of thousands of hectares to check first.",
 "SOLUSI KAMI": "OUR SOLUTION",
 "Dari Piksel Satelit ke Prioritas Lapangan": "From Satellite Pixels to Field Priorities",
 "Sistem menilai tiap sel gambut 1 km untuk peluang titik api dan penurunan muka air, lalu mengubah sel teratas menjadi tugas pemeriksaan bagi tim lapangan.": "The system scores each 1 km peat cell for hotspot probability and water-table drop, then turns the top cells into inspection tasks for field teams.",
 "Pemerintah daerah dan BPBD": "Local government and BPBD",
 "Melihat di mana risiko naik beberapa hari ke depan untuk merencanakan patroli dan penyekatan kanal.": "See where risk is rising days ahead, to plan patrols and canal blocking.",
 "Petugas lapangan": "Field officers",
 "Mendapat daftar singkat sel yang perlu diperiksa, lengkap dengan navigasi dan pencatatan status.": "Get a short list of cells to inspect, with navigation and status logging.",
 "Masyarakat (segera hadir)": "Communities (coming soon)",
 "Memeriksa status desanya dan melapor asap atau api dengan cepat. Halaman untuk warga belum tersedia.": "Check their village's status and report smoke or fire quickly. The community page is not available yet.",
 "Teknologi Kami": "Our Technology",
 "Data terbuka, model yang transparan, dan validasi yang bisa diperiksa": "Open data, transparent models, and validation you can check",
 "Fitur satelit": "Satellite features",
 "Titik api VIIRS (NASA FIRMS), kelembapan vegetasi NDMI, hujan, dan tutupan lahan; sebagian diolah di Google Earth Engine.": "VIIRS hotspots (NASA FIRMS), NDMI vegetation moisture, rainfall, and land cover; partly processed in Google Earth Engine.",
 "Data air tanah": "Groundwater data",
 "Muka air dari stasiun SiTMAT, digabung dengan kerapatan kanal dan indeks ENSO dan IOD.": "Water-table readings from SiTMAT stations, combined with canal density and ENSO and IOD indices.",
 "Pembelajaran mesin": "Machine learning",
 "Model gradient boosting (LightGBM) memperkirakan peluang titik api dan penurunan muka air per sel 1 km; status bukti ditampilkan apa adanya.": "Gradient-boosted models (LightGBM) predict hotspot probability and water-table drop per 1 km cell; evidence status is shown as it is.",
 "Pelaporan partisipatif": "Participatory reporting",
 "Formulir KoboToolbox memungkinkan tim lapangan dan warga melaporkan kejadian yang kembali dipakai untuk validasi.": "KoboToolbox forms let field teams and residents report events that feed back into validation.",
 "Bantu Kami Melindungi Gambut Indonesia": "Help Us Protect Indonesia's Peatlands",
 "Kami mencari mitra di pemerintah daerah, BPBD, dan masyarakat untuk menguji dan memvalidasi sistem ini di lapangan.": "We are looking for partners in local government, BPBD, and communities to pilot and validate the system on the ground.",
 "Kenali Tim Kami": "Meet Our Team",
 "KENALI TIM KAMI": "MEET OUR TEAM",
 "Orang-Orang di Balik Peringatan Ini": "The People Behind the Warning",
 "Mahasiswa magister Universitas Gadjah Mada yang membangun perangkat terbuka untuk pencegahan kebakaran gambut": "Master's students at Universitas Gadjah Mada building open tools for peatland fire prevention",
 "Tim Kami": "Our Team",
 "Memadukan penginderaan jauh, hidrologi, pembelajaran mesin, dan pelibatan masyarakat": "Combining remote sensing, hydrology, machine learning, and community engagement",
 "Peran belum diisi": "Role to be added",
 "Deskripsi singkat belum diisi.": "Short bio to be added.",
 "Dosen Pembimbing": "Our Academic Advisor",
 "Bimbingan dan keahlian dari dosen pembimbing kami": "Guidance and expertise from our supervising lecturer",
 "DOSEN PEMBIMBING": "ACADEMIC ADVISOR",
 "Associate Professor, Departemen Teknik Geodesi, Universitas Gadjah Mada": "Associate Professor, Department of Geodetic Engineering, Universitas Gadjah Mada",
 "LAPORAN LAPANGAN": "FIELD REPORT",
 "Lapor Asap atau Api": "Report Smoke or Fire",
 "Isi formulir singkat dari ponselmu. Laporan dipakai untuk memeriksa dan menilai prediksi, bukan sebagai peringatan resmi.": "Fill in a short form from your phone. Reports are used to check and score the forecasts, not as an official warning.",
 "Buka formulir laporan": "Open the report form",
 "Salin tautan": "Copy link",
 "Tautan disalin": "Link copied",
 "Kode tugas pemeriksaan": "Inspection task code",
 "Salin kode": "Copy code",
 "Kode disalin": "Code copied",
 "Tempel di isian \"Kode tugas pemeriksaan\" pada formulir.": "Paste it into the \"Kode tugas pemeriksaan\" (inspection task code) field of the form.",
 "Tiga langkah": "Three steps",
 "Formulir dibuka di KoboToolbox dan bisa diisi dari peramban ponsel.": "The form opens in KoboToolbox and can be filled in from your phone's browser.",
 "Siapkan": "Prepare",
 "Aktifkan GPS ponsel. Berdirilah sedekat mungkin dengan lokasi yang aman dan tunggu akurasi di bawah 20 m bila bisa. Siapkan foto.": "Turn on your phone's GPS. Stand as close as you safely can and wait for accuracy below 20 m if possible. Have a photo ready.",
 "Isi formulir": "Fill in the form",
 "Pilih apa yang dilaporkan, lalu jawab pertanyaan yang muncul. Jangan menulis nama orang atau siapa yang membakar.": "Choose what you are reporting, then answer the questions that appear. Do not write anyone's name or who started the fire.",
 "Kirim": "Send",
 "Laporan masuk ke KoboToolbox. Di peta hanya tampil sel 1 km, bukan titik laporanmu, dan identitas pelapor tidak disimpan.": "Your report goes to KoboToolbox. The map only shows a 1 km cell, not your report's location, and the reporter's identity is not stored.",
 "Apa yang bisa dilaporkan": "What you can report",
 "Tujuh jenis laporan; pertanyaan berikutnya menyesuaikan pilihanmu.": "Seven report types; the following questions adapt to your choice.",
 "Api menyala": "Flames visible",
 "Nyala api terlihat.": "You can see flames.",
 "Asap, nyala tidak terlihat": "Smoke, no visible flames",
 "Ada asap, tetapi api tidak tampak.": "There is smoke, but no flames are visible.",
 "Membara": "Smouldering",
 "Asap putih dari tanah, bau gambut, tanah hangat, tanpa nyala.": "White smoke from the ground, peat smell, warm soil, no flame.",
 "Sudah diperiksa, tidak ada kejadian": "Checked, nothing found",
 "Lokasi sudah dicek dan aman.": "The location was checked and is safe.",
 "Bacaan muka air": "Water-level reading",
 "Sumur pantau atau kanal; foto papan duga atau meteran.": "Monitoring well or canal; photo of the gauge board or tape.",
 "Kondisi sekat kanal": "Canal block condition",
 "Baik, rusak, atau jebol.": "Good, damaged, or breached.",
 "Tindakan di lapangan": "Action taken in the field",
 "Pembasahan, pemadaman, atau perbaikan sekat.": "Rewetting, firefighting, or block repair.",
 "SESUDAH DIKIRIM": "AFTER YOU SEND",
 "Laporanmu ikut menguji prediksi": "Your report helps test the forecasts",
 "Setiap laporan diberi tingkat keyakinan. Hanya tingkat A dan B yang dipakai menilai model.": "Every report gets a confidence level. Only levels A and B are used to score the model.",
 "Cocok dengan satelit": "Matches the satellite",
 "Atau dari petugas dengan foto dan GPS yang baik.": "Or from an officer with a photo and good GPS.",
 "Foto dengan GPS baik": "Photo with good GPS",
 "Atau dilaporkan oleh dua pelapor berbeda atau lebih.": "Or reported by two or more different reporters.",
 "Belum cukup": "Not enough yet",
 "Tetap dicatat, tetapi tidak dipakai menilai model.": "Still recorded, but not used to score the model.",
 "Dalam keadaan darurat": "In an emergency",
 "Formulir ini bukan saluran darurat. Bila ada api yang mengancam, hubungi BPBD atau petugas pemadam setempat lebih dulu.": "This form is not an emergency channel. If a fire is threatening, contact BPBD or your local firefighters first.",
 "Lihat halaman Respons": "See the Response page",
 "__partial": "Heads-up: the data panels, legends and map labels on this page are still in Indonesian. English for these is coming.",
 "__partial_close": "Close",
 "GEOFLAME": "GEOFLAME",
 "GSMaP, CHIRPS, ERA5-Land": "GSMaP, CHIRPS, ERA5-Land",
 "Universitas Gadjah Mada": "Universitas Gadjah Mada",
 "Yogyakarta, Indonesia": "Yogyakarta, Indonesia",
 "VIIRS + SiTMAT": "VIIRS + SiTMAT",
 "Fadhil": "Fadhil",
 "Arief": "Arief",
 "Laila": "Laila",
 "Indira": "Indira",
 "I Made Andi Arsana, S.T., M.E., Ph.D.": "I Made Andi Arsana, S.T., M.E., Ph.D.",
 "Wilayah": "Region",
 "Pilot: pesisir Jambi": "Pilot: coastal Jambi",
 "Monitoring: kondisi kini · GEOFLAME (prototipe)": "Monitoring: current conditions · GEOFLAME (prototype)",
 "Prediksi per sel 1 km · GEOFLAME (prototipe)": "Predictions per 1 km cell · GEOFLAME (prototype)",
 "Respons: laporan lapangan dan penilaian · GEOFLAME (prototipe)": "Response: field reports and scoring · GEOFLAME (prototype)",
 "Petugas: tugas pemeriksaan · GEOFLAME (prototipe)": "Field officers: inspection tasks · GEOFLAME (prototype)",
 "Kondisi kini": "Current conditions",
 "Angka diambil dari berkas keluaran pipeline. Estimasi riset, bukan peringatan resmi.": "Figures come from the pipeline output files. Research estimates, not an official warning.",
 "Angka ringkas": "Key figures",
 "Lihat sel prioritas": "View priority cells",
 "Buka prediksi": "Open predictions",
 "Titik api VIIRS, 7 hari": "VIIRS hotspots, 7 days",
 "hari ini": "today",
 "Harapan sel berapi besok": "Expected cells with fire tomorrow",
 "Stasiun di bawah −40 cm": "Stations below −40 cm",
 "Tugas pemeriksaan terbuka": "Open inspection tasks",
 "sama dengan 7 hari lalu": "same as 7 days ago",
 "perubahan 7 hari tidak lengkap": "7-day change incomplete",
 "belum ada data tugas": "no task data yet",
 "belum dimuat": "not loaded",
 "model belum dijalankan": "model not run yet",
 "Peta kerentanan per sel 1 km": "Susceptibility map per 1 km cell",
 "Kerentanan": "Susceptibility",
 "Titik api 7 hari": "Hotspots, 7 days",
 "Stasiun": "Stations",
 "Kanal": "Canals",
 "Lapisan peta": "Map layers",
 "Lanjutan": "Advanced",
 "Lapisan tambahan": "Extra layers",
 "Lapisan teknis": "Technical layers",
 "Bayangan relief": "Hillshade",
 "Batas KHG": "Peat hydrological unit (KHG) boundaries",
 "Batas kabupaten/provinsi": "District/province boundaries",
 "Opasitas peta": "Map opacity",
 "Tentang peta ini": "About this map",
 "Kerentanan relatif": "Relative susceptibility",
 "sangat tinggi": "very high",
 "tinggi": "high",
 "sedang": "medium",
 "rendah": "low",
 "sangat rendah": "very low",
 "Titik api, 7 hari": "Hotspots, 7 days",
 "Stasiun di atas ambang (≥ −40 cm)": "Stations above the threshold (≥ −40 cm)",
 "Indeks kondisi kini (indeks relatif)": "Current-condition index (relative index)",
 "Kerentanan struktural + tekanan dinamis.": "Structural susceptibility + dynamic pressure.",
 "Hanya kerentanan struktural (belum ada tekanan dinamis).": "Structural susceptibility only (no dynamic pressure yet).",
 "tanpa warna = bukan gambut, air, atau terbangun (tidak dinilai)": "no colour = not peat, water, or built-up (not assessed)",
 "Bayangan relief dari FABDEM; sinar dari barat laut; relief diperbesar 15x dan kontras diregangkan otomatis (relief gambut sangat landai; kesalahan vertikal DEM sebanding dengan relief).": "Hillshade from FABDEM; light from the north-west; relief exaggerated 15x and contrast stretched automatically (peat relief is very flat; DEM vertical error is comparable to the relief).",
 "Indeks relatif, bukan peluang kebakaran. Kelas dari ambang acuan tetap; kepercayaan ditunjukkan oleh transparansi dan arsiran.": "A relative index, not a fire probability. Classes use fixed reference breaks; confidence is shown by transparency and hatching.",
 "Kepercayaan peta": "Map confidence",
 "pekat: kepercayaan tinggi": "solid: high confidence",
 "agak transparan: sedang": "semi-transparent: medium",
 "transparan dan diarsir: rendah": "transparent and hatched: low",
 "Arsiran berarti jauh dari stasiun atau kondisi lahan berbeda dari stasiun.": "Hatching means far from stations, or land conditions unlike those at the stations.",
 "Titik api teramati (VIIRS)": "Observed hotspots (VIIRS)",
 "1–3 hari lalu": "1–3 days ago",
 "4–7 hari lalu": "4–7 days ago",
 "Ukuran lingkaran = daya radiasi api (FRP). Tanggal WIB; satelit Suomi NPP 375 m (NASA FIRMS).": "Circle size = fire radiative power (FRP). Dates in WIB (UTC+7); Suomi NPP satellite, 375 m (NASA FIRMS).",
 "Stasiun SiTMAT: muka air terakhir": "SiTMAT stations: latest water table",
 "di atas ambang (≥ −40 cm)": "above the threshold (≥ −40 cm)",
 "−40 s/d −80 cm": "−40 to −80 cm",
 "−80 s/d −120 cm": "−80 to −120 cm",
 "lebih dalam dari −120 cm": "deeper than −120 cm",
 "tanpa data": "no data",
 "berhenti melapor (> 3 hari)": "stopped reporting (> 3 days)",
 "Sel prioritas besok": "Priority cells for tomorrow",
 "Semua sel dan peluangnya": "All cells and their probabilities",
 "Kepercayaan model titik api: bukti terbatas": "Hotspot model confidence: limited evidence",
 "Kepercayaan model titik api": "Hotspot model confidence",
 "Muka air stasiun SiTMAT": "SiTMAT station water table",
 "30 hari terakhir · ambang −40 cm (garis putus-putus)": "Last 30 days · −40 cm threshold (dashed line)",
 "Deret waktu area pilot": "Pilot-area time series",
 "Ringkasan rata-rata area pilot (seluruh grid), bukan nilai per sel. Arahkan kursor ke grafik untuk membaca nilai.": "Averages over the pilot area (whole grid), not per-cell values. Hover over a chart to read values.",
 "90 hari": "90 days",
 "1 tahun": "1 year",
 "3 tahun": "3 years",
 "Rentang waktu": "Time range",
 "Muka air gambut (median stasiun)": "Peat water table (station median)",
 "Hujan 30 hari terakhir": "Rainfall, last 30 days",
 "Hari tanpa hujan berturut-turut": "Consecutive dry days",
 "Kelembapan tanah 0–7 cm": "Soil moisture 0–7 cm",
 "NDMI vegetasi (Sentinel-2)": "Vegetation NDMI (Sentinel-2)",
 "Titik api VIIRS per hari": "VIIRS hotspots per day",
 "teramati": "observed",
 "Jumlah hujan GSMaP 30 hari, rata-rata area pilot.": "30-day GSMaP rainfall total, pilot-area average.",
 "Rata-rata area pilot dari piksel GSMaP (0,1°).": "Pilot-area average of GSMaP pixels (0.1°).",
 "ERA5-Land (model reanalisis tanah mineral, bukan pengamatan gambut); tertinggal sekitar 9 hari.": "ERA5-Land (a reanalysis model for mineral soil, not peat observations); lags about 9 days.",
 "Komposit 30 hari, rata-rata area pilot; titik = akhir jendela. Makin rendah makin kering.": "30-day composites, pilot-area average; point = end of window. Lower means drier.",
 "Deteksi Suomi NPP 375 m di area pilot; tidak terdeteksi bukan berarti tidak ada api (awan dan asap menutup).": "Suomi NPP 375 m detections in the pilot area; no detection does not mean no fire (clouds and smoke can hide it).",
 "Unduh data deret waktu (JSON)": "Download time-series data (JSON)",
 "tidak ada data pada rentang ini": "no data in this range",
 "Belum tersedia.": "Not available yet.",
 "Laporan lapangan terbaru": "Latest field reports",
 "Belum ada laporan lapangan pada rentang data.": "No field reports in the data range yet.",
 "A = cocok dengan VIIRS, atau dari petugas dengan foto dan GPS baik. B = foto dengan GPS baik, atau dua pelapor berbeda atau lebih. C = belum cukup (tidak dipakai menilai model). Hanya sel 1 km; lokasi pelapor tidak ditampilkan.": "A = matches VIIRS, or from an officer with a photo and good GPS. B = photo with good GPS, or two or more different reporters. C = not enough (not used to score the model). 1 km cells only; reporter locations are not shown.",
 "Kejadian: laporan cocok dengan VIIRS": "Event: report matches VIIRS",
 "Kejadian dilaporkan": "Event reported",
 "Kunjungan tanpa kejadian": "Visit without event",
 "Faktor penyusun kondisi kini": "Components of current conditions",
 "● tersedia · ◐ sebagian · ○ belum tersedia": "● available · ◐ partial · ○ not yet available",
 "tersedia": "available",
 "sebagian": "partial",
 "belum tersedia": "not yet available",
 "Sensor muka air (SiTMAT)": "Water-level sensors (SiTMAT)",
 "Hujan (GSMaP, CHIRPS)": "Rainfall (GSMaP, CHIRPS)",
 "Indeks kelembapan tanah": "Soil-moisture index",
 "ENSO dan IOD (DMI)": "ENSO and IOD (DMI)",
 "Topografi (FABDEM) dan kanal": "Topography (FABDEM) and canals",
 "Tutupan lahan (WorldCover)": "Land cover (WorldCover)",
 "Titik api VIIRS": "VIIRS hotspots",
 "Prakiraan pengeringan per sel (7–14 hari)": "Per-cell drying forecast (7–14 days)",
 "· per sel": "· per cell",
 "· ERA5-Land 0–7 cm (reanalisis, bukan pengamatan gambut)": "· ERA5-Land 0–7 cm (reanalysis, not peat observations)",
 "· komposit bulanan per sel": "· monthly composite per cell",
 "· indeks bulanan": "· monthly indices",
 "· grid 100 m, grid induk equal-area": "· 100 m grid, equal-area master grid",
 "· 2021, tanpa kelas sawit": "· 2021, no oil-palm class",
 "Indeks kondisi kini memuat kerentanan struktural dan tekanan dinamis. Kalibrasi terhadap stasiun SiTMAT belum diuji.": "The current-condition index combines structural susceptibility and dynamic pressure. Calibration against SiTMAT stations has not been tested yet.",
 "Indeks kondisi kini baru memuat kerentanan struktural (kanal dan relief). Hujan, kelembapan tanah, dan muka air belum disertakan per sel.": "The current-condition index only includes structural susceptibility so far (canals and relief). Rainfall, soil moisture, and water table are not yet included per cell.",
 "Peta kerentanan belum dibuat (jalankan 07, 08, 10, lalu 09).": "The susceptibility map has not been built yet (run 07, 08, 10, then 09).",
 "Prototipe riset. Bukan peringatan resmi. Prediksi belum dikalibrasi; baca status validasi dan kelas kepercayaan sebelum memakai hasilnya.": "Research prototype. Not an official warning. Forecasts are not calibrated yet; read the validation status and confidence class before using the results.",
 "(c) OpenStreetMap contributors (ODbL); kanal dan batas gambut/KHG dari BRGM BlueBook 2026. Peta dasar: OpenStreetMap (tile standar; patuhi kebijakan tile OSM, ganti lewat manifest.basemap bila lalu lintas besar).": "(c) OpenStreetMap contributors (ODbL); canals and peat/KHG boundaries from BRGM BlueBook 2026. Basemap: OpenStreetMap (standard tiles; follow the OSM tile usage policy and switch via manifest.basemap for heavy traffic).",
 "Titik api: NRT/standar VIIRS 375 m Active Fire (VNP14IMG) dari NASA LANCE/FIRMS, doi:10.5067/FIRMS/VIIRS/VNP14IMGT_NRT.002; ikuti ketentuan sitasi dan penafian NASA LANCE/FIRMS saat membagikan ulang.": "Hotspots: VIIRS 375 m Active Fire NRT/standard (VNP14IMG) from NASA LANCE/FIRMS, doi:10.5067/FIRMS/VIIRS/VNP14IMGT_NRT.002; follow the NASA LANCE/FIRMS citation and disclaimer terms when redistributing.",
 "Hujan: JAXA GSMaP (Global Rainfall Map in Near-Real-Time) dan CHIRPS; citra: Copernicus Sentinel-1/2.": "Rainfall: JAXA GSMaP (Global Rainfall Map in Near-Real-Time) and CHIRPS; imagery: Copernicus Sentinel-1/2.",
 "Muka air dan stasiun: SiTMAT (KLH/BRGM), diambil dengan jeda sopan; data dapat berubah atau terkoreksi.": "Water table and stations: SiTMAT (KLH/BRGM), fetched with polite delays; data may change or be corrected.",
 "Tutupan lahan: ESA WorldCover 10 m 2021 (CC BY 4.0).": "Land cover: ESA WorldCover 10 m 2021 (CC BY 4.0).",
 "FABDEM is produced using Copernicus WorldDEM-30 (c) DLR e.V. (CC BY-NC-SA 4.0), Hawker dkk. 2022.": "FABDEM is produced using Copernicus WorldDEM-30 (c) DLR e.V. (CC BY-NC-SA 4.0), Hawker et al. 2022.",
 "Atribusi dan penafian": "Attribution and disclaimer",
 "Memuat...": "Loading...",
 "Deret waktu tidak tersedia.": "Time series not available.",
 "Prakiraan muka air (prototipe)": "Water-table forecast (prototype)",
 "Belum ada prakiraan untuk stasiun ini.": "No forecast for this station yet.",
 "Belum ada prediksi untuk stasiun ini.": "No prediction for this station yet.",
 "Prakiraan belum dapat diandalkan: model belum terbukti lebih baik daripada tebakan \"muka air tetap\". Angka hanya untuk tinjauan.": "The forecast is not reliable yet: the model has not been shown to beat the guess \"water table unchanged\". Numbers are for review only.",
 "stabil dalam 7 hari terakhir": "stable over the last 7 days",
 "perubahan 7 hari tidak tersedia": "7-day change not available",
 "Pengamatan satelit 375 m; tidak terdeteksi bukan berarti tidak ada api (awan dan asap menutup).": "375 m satellite observation; no detection does not mean no fire (clouds and smoke can hide it).",
 "Ringkasan tingkat unit; perbesar peta untuk melihat sel.": "Unit-level summary; zoom in to see cells.",
 "blok 5 km (sementara, tanpa batas KHG)": "5 km block (temporary, no KHG boundaries)",
 "Kelas:": "Class:",
 "per blok 5 km": "per 5 km block",
 "sel 500 m": "500 m cells",
 "sel 100 m": "100 m cells",
 "lapisan mati": "layer off",
 "sumatra": "Sumatra",
 "kalimantan": "Kalimantan",
 "papua": "Papua",
 "turun": "down",
 "naik": "up",
 "tetap": "unchanged",
 "malam": "night",
 "siang": "day",
 "Validasi belum tersedia. Perlakukan prediksi sebagai prototipe.": "Validation not available yet. Treat the forecasts as a prototype.",
 "Prediksi per sel 1 km": "Predictions per 1 km cell",
 "Peluang, bukan kepastian. Klik sel untuk melihat rinciannya. · Terbit": "Probabilities, not certainties. Click a cell to see its details. · Issued",
 "Peluang, bukan kepastian. Klik sel untuk melihat rinciannya.": "Probabilities, not certainties. Click a cell to see its details.",
 "Tema prediksi": "Prediction theme",
 "Horizon waktu": "Time horizon",
 "Peluang titik api": "Hotspot probability",
 "Pengeringan muka air": "Water-table drying",
 "Besok": "Tomorrow",
 "3 hari": "3 days",
 "7 hari": "7 days",
 "14 hari": "14 days",
 "30 hari": "30 days",
 "semua": "all",
 "Status bukti model": "Model evidence status",
 "Titik api: bukti terbatas": "Hotspots: limited evidence",
 "Pengeringan per sel: belum terbukti": "Per-cell drying: not yet proven",
 "Prakiraan stasiun: belum terbukti": "Station forecast: not yet proven",
 "Titik api": "Hotspots",
 "Pengeringan per sel": "Per-cell drying",
 "Prakiraan stasiun": "Station forecast",
 "belum terbukti": "not yet proven",
 "bukti terbatas": "limited evidence",
 "belum ada": "none yet",
 "Peta peluang": "Probability map",
 "Peluang ada titik api besok": "Probability of a hotspot tomorrow",
 "Peluang ada titik api dalam 3 hari": "Probability of a hotspot within 3 days",
 "Peluang muka air turun ≥ 10 cm dalam 7 hari": "Probability of a ≥ 10 cm water-table drop within 7 days",
 "Peluang muka air turun ≥ 10 cm dalam 14 hari": "Probability of a ≥ 10 cm water-table drop within 14 days",
 "Peluang muka air turun ≥ 10 cm, 7 hari": "Probability of a ≥ 10 cm drop, 7 days",
 "Peluang turun ≥ 10 cm, 14 hari": "Probability of a ≥ 10 cm drop, 14 days",
 "Garis tebal = sel terpilih": "Thick outline = selected cell",
 "Warna dipucatkan: model belum terbukti mengalahkan pembanding.": "Faded colours: the model has not yet been shown to beat the baselines.",
 "Kerentanan struktural (konteks)": "Structural susceptibility (context)",
 "SEL TERPILIH": "SELECTED CELL",
 "Peluang titik api besok": "Hotspot probability tomorrow",
 "Dalam 3 hari": "Within 3 days",
 "Kepercayaan model:": "Model confidence:",
 "Pengeringan 14 hari untuk sel ini:": "14-day drying for this cell:",
 "Peluang titik api besok untuk sel ini:": "Hotspot probability tomorrow for this cell:",
 "Faktor pendorong per sel belum diekspor oleh model (perlu keluaran faktor dari skrip 14 dan 15), jadi tidak ditampilkan.": "Per-cell drivers are not yet exported by the model (requires driver output from scripts 14 and 15), so they are not shown.",
 "Mengapa sel ini tinggi?": "Why is this cell high?",
 "Sel teratas peluang titik api": "Top cells by hotspot probability",
 "Sel teratas peluang pengeringan": "Top cells by drying probability",
 "Ringkasan prakiraan": "Forecast summary",
 "Harapan sel 1 km berapi besok:": "Expected 1 km cells with fire tomorrow:",
 "Sel teratas digambar:": "Top cells drawn:",
 "Pengeringan 14 hari: peluang rata-rata": "14-day drying: mean probability",
 "Masukan model": "Model inputs",
 "Seberapa jauh model bisa dipercaya?": "How far can the model be trusted?",
 "Untuk juri dan peneliti · angka dari berkas keluaran": "For judges and researchers · figures from output files",
 "Titik api besok: model lawan pembanding": "Hotspots tomorrow: model vs baselines",
 "Model": "Model",
 "Klimatologi": "Climatology",
 "Persistensi": "Persistence",
 "Tugas teratas lawan acak": "Top-ranked vs random tasks",
 "Belum ada penilaian prospektif. Jalankan 18, lalu 20 dan 21.": "No prospective scoring yet. Run 18, then 20 and 21.",
 "Cara pengujian": "How it was tested",
 "Dibandingkan dengan pembanding sederhana: klimatologi dan persistensi": "Compared with simple baselines: climatology and persistence",
 "Penilaian prospektif (arsip prediksi lawan kejadian): belum ada": "Prospective scoring (forecast archive vs events): none yet",
 "Pengeringan per sel: uji ruang-waktu": "Per-cell drying: space-time test",
 "Sel prioritas model": "Model priority cells",
 "Sel acak": "Random cells",
 "Metrik belum diekspor (jalankan 14, lalu 09).": "Metrics not exported yet (run 14, then 09).",
 "Metrik belum diekspor (jalankan 15, lalu 09).": "Metrics not exported yet (run 15, then 09).",
 "tidak termasuk sel teratas yang diekspor (peluang sel ini tidak tersedia)": "not among the exported top cells (probability for this cell not available)",
 "sel ini tidak dinilai model pengeringan": "this cell is not scored by the drying model",
 "di bawah 3% (tetap 5% teratas)": "below 3% (still in the top 5%)",
 "peluang ≥ 30%": "probability ≥ 30%",
 "Model titik api belum dijalankan.": "The hotspot model has not been run yet.",
 "Model pengeringan per sel belum dijalankan.": "The per-cell drying model has not been run yet.",
 "Belum ada prediksi (jalankan 13 dan 14, lalu 09).": "No predictions yet (run 13 and 14, then 09).",
 "Belum ada prediksi (jalankan 13, 14, dan 15, lalu 09).": "No predictions yet (run 13, 14 and 15, then 09).",
 "Belum terbukti mengalahkan pembanding sederhana pada uji; perlakukan sebagai petunjuk.": "Not yet shown to beat simple baselines in testing; treat as a hint.",
 "Belum terbukti lebih baik daripada \"muka air tetap\" pada stasiun baru dan tanggal baru; perlakukan sebagai petunjuk.": "Not yet shown to beat \"water table unchanged\" at new stations and dates; treat as a hint.",
 "teratas": "top",
 "Data belum dapat dimuat": "Data could not be loaded",
 "Respons: laporan lapangan dan penilaian": "Response: field reports and scoring",
 "Apa yang ditambahkan laporan warga dan petugas pada pengamatan satelit, tugas pemeriksaan dari prediksi, dan apakah prediksi terbukti.": "What reports from residents and officers add to satellite observations, the inspection tasks drawn from the forecasts, and whether the forecasts held up.",
 "Prototipe riset, bukan peringatan resmi. Tingkat keyakinan laporan memakai aturan awal yang belum disetel.": "Research prototype, not an official warning. Report confidence levels use initial rules that have not been tuned yet.",
 "Bandingkan": "Compare",
 "Hanya satelit": "Satellite only",
 "Satelit + laporan lapangan": "Satellite + field reports",
 "Rentang waktu:": "Time range:",
 "Tanggal akhir rentang": "Range end date",
 "Panjang rentang": "Range length",
 "Sebelum dan sesudah laporan": "Before and after reports",
 "sel-hari pada rentang ini": "cell-days in this range",
 "Dengan laporan": "With reports",
 "Kejadian tercatat": "Events recorded",
 "dikonfirmasi di lapangan": "confirmed in the field",
 "sel baru di sebelah deteksi satelit": "new cell next to a satellite detection",
 "lolos dari satelit": "missed by satellite",
 "di antaranya membara": "of which smouldering",
 "Diperiksa, tidak ada kejadian": "Checked, no event",
 "Laporan belum terverifikasi": "Unverified reports",
 "Sel-hari dikunjungi": "Cell-days visited",
 "Sel-hari dengan tindakan": "Cell-days with action",
 "Lapisan": "Layers",
 "Tugas pemeriksaan (terbitan terakhir)": "Inspection tasks (latest issue)",
 "Sel berpeluang tertinggi (prediksi)": "Highest-probability cells (prediction)",
 "Sekat kanal": "Canal blocks",
 "Muka air lapangan": "Field water levels",
 "Tugas pemeriksaan": "Inspection tasks",
 "Apakah prediksi terbukti?": "Did the forecasts hold up?",
 "arsip prediksi lawan kejadian sesudahnya": "forecast archive vs later events",
 "Belum ada skor. Jalankan 18_score_prospective.py lalu 20_export_response.py.": "No scores yet. Run 18_score_prospective.py, then 20_export_response.py.",
 "Indeks kerentanan lawan muka air lapangan.": "Susceptibility index vs field water levels.",
 "belum ada bacaan muka air pada bulan yang dipilih": "no water-level readings in the selected month yet",
 "Kejadian per sel 1 km": "Events per 1 km cell",
 "Satelit dan laporan lapangan": "Satellite and field reports",
 "Hanya satelit (belum ada laporan)": "Satellite only (no reports yet)",
 "Hanya laporan, tingkat A/B (lolos dari satelit)": "Reports only, level A/B (missed by satellite)",
 "Hanya laporan A/B (lolos dari satelit)": "Reports only, A/B (missed by satellite)",
 "Laporan belum terverifikasi (tingkat C)": "Unverified report (level C)",
 "Laporan belum terverifikasi (C)": "Unverified report (C)",
 "Ada laporan membara": "Smouldering reported",
 "Sel berpeluang tertinggi": "Highest-probability cells",
 "Sel 1 km yang harus dicek petugas": "1 km cells that officers must check",
 "Belum diperiksa (kotak kosong)": "Not yet checked (empty square)",
 "Sudah diperiksa (kotak terisi)": "Checked (filled square)",
 "Sekat kanal (kondisi terakhir)": "Canal blocks (latest condition)",
 "Muka air lapangan (bacaan terakhir)": "Field water levels (latest reading)",
 "Sel 1 km, bukan titik laporan (privasi pelapor). Tanpa warna = tidak ada bukti, bukan berarti aman.": "1 km cells, not report points (reporter privacy). No colour = no evidence, not the same as safe.",
 "Dikonfirmasi lapangan": "Confirmed in the field",
 "Lolos dari satelit": "Missed by satellite",
 "Tugas belum dicek petugas": "Tasks not yet checked",
 "TUGAS PEMERIKSAAN": "INSPECTION TASK",
 "Belum diperiksa": "Not yet checked",
 "Diperiksa: tidak ada kejadian": "Checked: no event",
 "Diperiksa: ada kejadian": "Checked: event found",
 "Laporkan hasil pemeriksaan": "Report inspection result",
 "Kondisi terakhir:": "Latest condition:",
 "baik": "good",
 "rusak": "damaged",
 "jebol": "breached",
 "ada tindakan": "action taken",
 "konflik: nihil dan kejadian di sel-hari yang sama": "conflict: nothing found and an event on the same cell-day",
 "kunjungan lain (muka air atau sekat)": "other visit (water level or block)",
 "DATA TIRUAN.": "SYNTHETIC DATA.",
 "DATA TIRUAN": "SYNTHETIC DATA",
 "Laporan di halaman ini buatan untuk menguji alur. Angka di bawah bukan bukti kinerja.": "Reports on this page were generated to test the workflow. The numbers below are not evidence of performance.",
 "Tugas pemeriksaan Belum ada daftar tugas (19).": "Inspection tasks: no task list yet (19).",
 "Belum ada daftar tugas (19).": "No task list yet (19).",
 "Saring tugas": "Filter tasks",
 "Semua": "All",
 "Terbuka": "Open",
 "Selesai": "Done",
 "Belum mulai": "Not started",
 "Dalam perjalanan": "On the way",
 "Sudah diperiksa": "Checked",
 "Tidak terjangkau": "Unreachable",
 "Navigasi": "Navigate",
 "Perbarui status": "Update status",
 "Status tugas": "Task status",
 "Status lapangan": "Field status",
 "Waktu kunjungan (WIB)": "Visit time (WIB)",
 "Catatan (opsional, tanpa nama orang)": "Note (optional, no personal names)",
 "mis. akses lewat kanal, jalan terputus": "e.g. access via canal, road cut off",
 "Kunci tim (PEAT_API_TOKEN)": "Team key (PEAT_API_TOKEN)",
 "Batal": "Cancel",
 "Simpan status": "Save status",
 "Mode demo: server API tidak berjalan, status hanya tersimpan di peramban ini.": "Demo mode: the API server is not running; status is only saved in this browser.",
 "Terhubung ke server API: status disimpan tambah-saja.": "Connected to the API server: status is saved append-only.",
 "Isi waktu kunjungan.": "Fill in the visit time.",
 "Hasil Kobo: ada kejadian": "Kobo result: event found",
 "Kejadian yang teramati (api, asap) dilaporkan lewat formulir KoboCollect. Status di sini hanya catatan kunjungan. Alasan dan peluang tiap tugas sengaja tidak ditampilkan agar pemeriksa tetap buta terhadap prediksi.": "Observed events (fire, smoke) are reported through the KoboCollect form. The status here is only a visit log. The reason and probability of each task are deliberately hidden so inspectors stay blind to the forecast.",
 "Server API tidak berjalan; perubahan tidak bisa disimpan.": "The API server is not running; changes cannot be saved.",
 "Tugas belum dapat dimuat:": "Tasks could not be loaded:",
 "(jalankan 20 dan 21, lalu buka lewat server).": "(run 20 and 21, then open via the server).",
 "ya": "yes",
 "belum": "not yet",
 "membara": "smouldering",
 "api": "fire",
 "asap": "smoke",
 "nominal": "nominal",
 "Dalam 3 hari:": "Within 3 days:",
 "Peluang ada titik api besok:": "Probability of a hotspot tomorrow:",
 "Memuat data...": "Loading data...",
 "Memuat tugas...": "Loading tasks...",
 "Peluang": "Probability",
 "Klik sel di peta atau pilih dari daftar di bawah.": "Click a cell on the map or pick one from the list below.",
 "Sel teratas": "Top cells",
 "Gagal memuat data:": "Failed to load data:",
 "Hasil Kobo: nihil": "Kobo result: nothing found",
 "data/response.json belum ada. Jalankan python scripts/20_export_response.py": "data/response.json does not exist yet. Run python scripts/20_export_response.py",
 "Deret waktu belum dibuat. Jalankan: python scripts/09b_export_timeseries.py (atau ./run_pipeline.sh peta).": "The time series has not been built yet. Run: python scripts/09b_export_timeseries.py (or ./run_pipeline.sh peta).",
 "U": "N"
};
