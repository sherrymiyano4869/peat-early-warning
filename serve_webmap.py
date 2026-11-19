#!/usr/bin/env python3
"""serve_webmap.py: server statis webmap TANPA cache peramban (lokal, bukan dari zip web).

    python serve_webmap.py [PORT]        # bawaan 8000; lalu buka http://localhost:8000

Pengganti `python -m http.server -d webmap 8000`: server bawaan tidak mengirim aturan cache, sehingga peramban memakai salinan lama
berkas .js dan .css (gejala: tampilan tidak berubah setelah pembaruan). Di sini setiap jawaban memakai Cache-Control: no-store.
"""
import functools
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class NoCache(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    root = Path(__file__).resolve().parent / "webmap"
    handler = functools.partial(NoCache, directory=str(root))
    print(f"Webmap tanpa cache: http://localhost:{port}  (Ctrl+C untuk berhenti)")
    ThreadingHTTPServer(("0.0.0.0", port), handler).serve_forever()
