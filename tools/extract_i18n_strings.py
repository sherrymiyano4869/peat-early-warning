#!/usr/bin/env python3
"""extract_i18n_strings.py: daftar teks statis (HTML) dan string (JS) yang belum punya terjemahan Inggris.

    python tools/extract_i18n_strings.py            # cetak ringkasan per berkas
    python tools/extract_i18n_strings.py --tsv docs/i18n_belum_diterjemahkan.tsv

Kunci kamus = teks Indonesia persis (spasi dinormalkan) di webmap/i18n-en.js. Teks HTML diambil sama seperti i18n.js menelusuri DOM
(simpul teks dan atribut aria-label, title, alt, placeholder). String JS hanya perkiraan (literal >= 14 karakter): pakai window.I18N.t()
pada string yang disusun di kode, lalu tambahkan pasangannya ke kamus.
"""
import argparse
import glob
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "webmap"
ATTRS = ("aria-label", "title", "alt", "placeholder")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


class Collect(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        for k, v in attrs:
            if k in ATTRS and v:
                self.out.append(norm(v))

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            t = norm(data)
            if t:
                self.out.append(t)


def html_strings(path: Path):
    p = Collect()
    p.feed(path.read_text(encoding="utf-8"))
    return [s for s in p.out if re.search(r"[A-Za-z]{3}", s)]


def js_strings(path: Path):
    s = path.read_text(encoding="utf-8")
    return [norm(m) for m in re.findall(r"(?:\"|`)([^\"`\n]{14,}?)(?:\"|`)", s) if re.search(r"[A-Za-z]{4}", m) and " " in m and "${" not in m]


def load_dict():
    f = WEB / "i18n-en.js"
    if not f.exists():
        return {}
    txt = f.read_text(encoding="utf-8")
    m = re.search(r"window\.I18N_EN\s*=\s*(\{.*\});?\s*$", txt, re.S)
    return json.loads(m.group(1)) if m else {}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tsv")
    args = ap.parse_args()
    d = load_dict()
    rows = []
    for f in sorted(glob.glob(str(WEB / "*.html"))):
        for s in dict.fromkeys(html_strings(Path(f))):
            if s not in d:
                rows.append((Path(f).name, s))
    for f in sorted(glob.glob(str(WEB / "*.js"))):
        name = Path(f).name
        if name.startswith("i18n"):
            continue
        for s in dict.fromkeys(js_strings(Path(f))):
            if s not in d:
                rows.append((name, s))
    per = {}
    for f, s in rows:
        per[f] = per.get(f, 0) + 1
    print(f"kamus: {len(d)} entri; belum diterjemahkan: {len(rows)} string")
    for f, n in sorted(per.items()):
        print(f"  {f:18s} {n}")
    if args.tsv:
        with open(args.tsv, "w", encoding="utf-8") as fh:
            fh.write("berkas\tindonesia\tinggris\n")
            for f, s in rows:
                fh.write(f"{f}\t{s}\t\n")
        print("tersimpan:", args.tsv)


if __name__ == "__main__":
    main()
