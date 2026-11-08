"""Uji lokal polite_http tanpa menyentuh internet.

Jalankan dari folder proyek:
    python scripts/test_polite_http.py
"""
import json
import shutil
import sys
import tempfile
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.polite_http import PoliteClient


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):  # matikan log di terminal
        pass


def main() -> None:
    tmp = Path(tempfile.mkdtemp())
    (tmp / "stations.json").write_text(json.dumps({"stations": [1, 2, 3]}))

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(tmp)))
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    client = PoliteClient(tmp / "cache", min_interval=1.0)
    url = f"http://127.0.0.1:{port}/stations.json"

    t0 = time.monotonic()
    first = client.get_json(url)
    t1 = time.monotonic()
    second = client.get_json(url)               # harus dari cache
    t2 = time.monotonic()
    client.get_json(url, params={"page": 2})    # permintaan baru, harus kena jeda
    t3 = time.monotonic()

    print("data :", first, "| sama dengan cache:", first == second)
    print(f"cache cepat      : {t2 - t1:.3f} s  (harapan < 0.2) -> {'OK' if t2 - t1 < 0.2 else 'GAGAL'}")
    print(f"jeda antar unduh : {t3 - t2:.3f} s  (harapan >= 0.8) -> {'OK' if t3 - t2 >= 0.8 else 'GAGAL'}")
    print("berkas cache     :", len(list((tmp / 'cache').glob('*.json'))), "(harapan 2)")

    server.shutdown()
    shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
