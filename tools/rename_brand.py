"""rename_brand: ganti nama situs webmap menjadi GEOFLAME dan pasang tagline di bawah nama (bilah atas).

    python tools/rename_brand.py            # hanya melaporkan, belum menulis apa pun
    python tools/rename_brand.py --apply    # menerapkan; tinjau dengan: git diff webmap

Yang diubah:
    webmap/*.html   nama di bilah atas (+ tagline), judul tab, nama di footer, "© 2026 Tim ..."
    webmap/i18n-en.js   kunci dan nilai kamus yang menyebut nama lama (nama sama di ID dan EN), + entri tagline ID -> EN
    webmap/pages.css    gaya tagline (tampil >= 1700 px, dua baris kecil; disembunyikan di bawahnya)
Bisa diulang tanpa efek ganda. Berkas lokal (tidak ada di zip web).
"""
import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "webmap"

OLD = "Peatland Early Warning"
NEW = "GEOFLAME"
OLD_TITLE_TAIL = "peringatan dini kekeringan gambut (prototipe)"     # judul tab Respons dan Petugas
NEW_TITLE_TAIL = f"{NEW} (prototipe)"
TAG_ID = ("Platform geospasial berbasis AI untuk memantau, memprediksi, dan merespons kebakaran gambut "
          "dengan lebih cepat, lebih tepat, dan lebih efektif")
TAG_EN = ("AI-powered geospatial platform to monitor, predict, and respond to peatland fires "
          "faster, more precisely, and more effectively")
CSS_MARK = "/* tagline merek (rename_brand.py) */"
CSS = f"""
{CSS_MARK}
.brand small.tagline {{ display: none; max-width: 420px; font-size: 11px; line-height: 1.35; color: #E5C9B8; white-space: normal; }}
@media (min-width: 1700px) {{ .brand small.tagline {{ display: block; }} .topnav a {{ white-space: nowrap; }} }}
"""


def fix_html(t: str) -> str:
    # bilah atas: <span><b>NAMA</b></span>  ->  <span><b>GEOFLAME</b><small class="tagline">...</small></span>
    t = re.sub(r'(<a class="brand"[^>]*>.*?<span>)<b>[^<]*</b>(?:<small[^>]*>.*?</small>)?(</span>)',
               lambda m: f'{m.group(1)}<b>{NEW}</b><small class="tagline">{TAG_ID}</small>{m.group(2)}', t, count=1, flags=re.S)
    t = t.replace(OLD_TITLE_TAIL, NEW_TITLE_TAIL)
    t = t.replace(OLD, NEW)
    return t


def fix_dict(t: str) -> str:
    t = t.replace(f'"Response: field reports and scoring · peatland drought early warning (prototype)"',
                  f'"Response: field reports and scoring · {NEW} (prototype)"')
    t = t.replace(f'"Field officers: inspection tasks · peatland drought early warning (prototype)"',
                  f'"Field officers: inspection tasks · {NEW} (prototype)"')
    t = t.replace(OLD_TITLE_TAIL, NEW_TITLE_TAIL)
    t = t.replace(f"© 2026 {OLD} team", f"© 2026 {NEW} team")
    t = t.replace(OLD, NEW)
    if f'"{TAG_ID}"' not in t:
        t = re.sub(r"(window\.I18N_EN\s*=\s*\{)", lambda m: f'{m.group(1)}\n "{TAG_ID}": "{TAG_EN}",', t, count=1)
    return t


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="tulis perubahan (tanpa ini hanya laporan)")
    args = ap.parse_args()
    jobs = [(f, fix_html) for f in sorted(WEB.glob("*.html"))] + [(WEB / "i18n-en.js", fix_dict)]
    changed = 0
    for f, fn in jobs:
        old = f.read_text(encoding="utf-8")
        new = fn(old)
        if new != old:
            changed += 1
            print(f"  ubah  {f.relative_to(ROOT)}  ({old.count(OLD)} sebutan nama lama)")
            if args.apply:
                f.write_text(new, encoding="utf-8")
    css = WEB / "pages.css"
    if CSS_MARK not in css.read_text(encoding="utf-8"):
        changed += 1
        print(f"  ubah  {css.relative_to(ROOT)}  (gaya tagline)")
        if args.apply:
            with css.open("a", encoding="utf-8") as fh:
                fh.write(CSS)
    others = [p for p in WEB.glob("*.js") if p.name != "i18n-en.js" and OLD in p.read_text(encoding="utf-8")]
    for p in others:
        print(f"  CATATAN: {p.relative_to(ROOT)} masih menyebut nama lama, sunting manual")
    if not changed:
        print("Tidak ada yang perlu diubah (sudah GEOFLAME).")
    elif not args.apply:
        print(f"{changed} berkas akan diubah. Jalankan lagi dengan --apply.")
    else:
        print(f"{changed} berkas diubah. Tinjau: git diff webmap")


if __name__ == "__main__":
    main()
