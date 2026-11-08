"""Cetak struktur sebuah berkas JSON: jalur kunci, tipe, jumlah, dan contoh nilai.

    python scripts/inspect_json.py berkas.json

Bisa dipakai juga pada berkas cache PolitClient (data/raw/sitmat/*.json);
bagian "data"-nya yang diperiksa.
"""
import json
import sys
from pathlib import Path


def short(value, limit: int = 160) -> str:
    return json.dumps(value, ensure_ascii=False)[:limit]


def walk(node, path: str = "$") -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            walk(value, f"{path}.{key}")
    elif isinstance(node, list):
        print(f"{path}: list[{len(node)}]")
        if node:
            if isinstance(node[0], dict):
                print(f"    kunci  : {list(node[0].keys())}")
            print(f"    pertama: {short(node[0])}")
            if len(node) > 1:
                print(f"    terakhir: {short(node[-1])}")
    else:
        print(f"{path}: {type(node).__name__} = {short(node, 100)}")


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Pemakaian: python scripts/inspect_json.py berkas.json")
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if isinstance(data, dict) and {"url", "fetched_at", "data"} <= data.keys():
        print("(berkas cache PoliteClient)", data["url"], data["fetched_at"])
        data = data["data"]
    walk(data)


if __name__ == "__main__":
    main()
