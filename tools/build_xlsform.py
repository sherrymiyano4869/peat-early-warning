"""build_xlsform: tulis formulir laporan lapangan (XLSForm untuk KoboToolbox/ODK) dari skema di src/reports.py.

    python tools/build_xlsform.py            # -> forms/laporan_lapangan.xlsx; unggah ke KoboToolbox (Deploy), isi lewat KoboCollect (bisa tanpa sinyal)

Nama kolom formulir = nama yang dibaca 16_ingest_reports.py; ubah pilihan di src/reports.py lalu bangun ulang, jangan sunting xlsx langsung.
"""
import sys
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.reports import JENIS, KONDISI_SEKAT, PELAPOR, TINDAKAN  # noqa: E402

SURVEY = [  # type, name, label, required, relevant, constraint, hint, parameters
    ("dateTime", "waktu_amat", "Kapan Anda melihatnya?", "yes", "", ". <= now()", "Waktu pengamatan, bukan waktu mengirim"),
    ("geopoint", "lokasi", "Lokasi (berdiri sedekat mungkin yang aman)", "yes", "", "", "Tunggu akurasi di bawah 20 m bila bisa"),
    ("select_one jenis", "jenis", "Apa yang dilaporkan?", "yes", "", "", ""),
    ("image", "foto", "Foto", "", "", "", "Untuk muka air: foto papan duga atau meteran", "max-pixels=1280"),
    ("decimal", "kedalaman_cm", "Kedalaman muka air dari permukaan tanah (cm)", "yes", "${jenis} = 'muka_air'", ". >= -100 and . <= 300",
     "0 bila air tepat di permukaan; negatif bila tergenang"),
    ("text", "titik_acuan", "Kode titik (sumur pantau, papan duga, atau sekat)", "", "${jenis} = 'muka_air' or ${jenis} = 'sekat'", "", "Pakai kode yang sama tiap kali"),
    ("select_one kondisi_sekat", "kondisi_sekat", "Kondisi sekat kanal", "yes", "${jenis} = 'sekat'", "", ""),
    ("select_one jenis_tindakan", "jenis_tindakan", "Tindakan yang dilakukan", "yes", "${jenis} = 'tindakan'", "", ""),
    ("select_one pelapor", "pelapor", "Anda melapor sebagai", "yes", "", "", ""),
    ("text", "kode_pelapor", "Kode pelapor", "", "", "", "Kode dari koordinator; jangan isi nama"),
    ("text", "id_tugas", "Kode tugas pemeriksaan (bila ada)", "", "", "", "Tertulis di daftar tugas, mis. T20261112-007"),
    ("text", "catatan", "Catatan", "", "", "", "Jangan menulis nama orang atau siapa yang membakar"),
]


def main() -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "survey"
    ws.append(["type", "name", "label", "required", "relevant", "constraint", "hint", "parameters"])
    for row in SURVEY:
        ws.append(row)
    ch = wb.create_sheet("choices")
    ch.append(["list_name", "name", "label"])
    for list_name, items in (("jenis", JENIS), ("pelapor", PELAPOR), ("kondisi_sekat", KONDISI_SEKAT), ("jenis_tindakan", TINDAKAN)):
        for name, label in items.items():
            ch.append([list_name, name, label])
    st = wb.create_sheet("settings")
    st.append(["form_title", "form_id", "version"])
    st.append(["Laporan lapangan gambut", "laporan_lapangan", "1"])
    out = ROOT / "forms" / "laporan_lapangan.xlsx"
    out.parent.mkdir(exist_ok=True)
    wb.save(out)
    print(f"{out}: {len(SURVEY)} pertanyaan")


if __name__ == "__main__":
    main()
