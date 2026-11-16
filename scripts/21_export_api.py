"""21_export_api: cermin statis API v1 di webmap/data/v1 untuk hosting tanpa server (bentuk respons sama dengan api/app.py).

    python scripts/21_export_api.py [--out webmap/data] [--openapi docs/api/openapi.json]

Masuk : webmap/data dari 09, 10, dan 20; opsional data/interim/task_updates.sqlite (status lapangan tugas)
Keluar: webmap/data/v1/{meta,collections,susceptibility,layers,validation,scores}.json,
        v1/collections/<id>/items.json (tanpa penyaring), v1/stations/<id>/series.json
Mode statis tidak punya penyaring, item tunggal, atau PATCH; alamatnya = alamat server + ".json".
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.api_store import COLLECTIONS, DataStore, MissingData
from src.common import ROOT, path
from src.task_updates import TaskUpdates


def write(f: Path, obj) -> None:
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def export(data_dir: Path, db: Path) -> list[str]:
    """Tulis cermin v1; kembalikan daftar sumber daya yang dilewati karena datanya belum ada."""
    store, out, skipped = DataStore(data_dir, task_status=TaskUpdates(db).latest), data_dir / "v1", []
    jobs = {name: getattr(store, name) for name in ("meta", "collections", "susceptibility", "layers", "validation", "scores")}
    jobs |= {f"collections/{cid}/items": (lambda cid=cid: store.query(cid, {})) for cid in COLLECTIONS}
    for rel, fn in jobs.items():
        try:
            write(out / f"{rel}.json", fn())
        except MissingData:
            skipped.append(rel)
    try:
        for f in store.features("stations")[0]:
            write(out / "stations" / f["id"] / "series.json", store.series(f["id"]))
    except MissingData:
        skipped.append("stations/*/series")
    return skipped


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / "webmap" / "data"))
    ap.add_argument("--openapi", help="tulis juga skema OpenAPI (untuk diimpor Postman), mis. docs/api/openapi.json")
    args = ap.parse_args()
    skipped = export(Path(args.out), path("interim") / "task_updates.sqlite")
    print(f"cermin v1: {Path(args.out) / 'v1'}" + (f" | dilewati (data belum ada): {', '.join(skipped)}" if skipped else ""))
    if args.openapi:
        from api.app import create_app
        write(Path(args.openapi), create_app(data_dir=Path(args.out)).openapi())
        print("OpenAPI:", args.openapi)


if __name__ == "__main__":
    main()
