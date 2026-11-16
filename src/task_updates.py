"""Status lapangan tugas pemeriksaan: catatan tambah-saja (append-only) di SQLite.

Ini status alur kerja (belum, dalam_perjalanan, diperiksa, tidak_terjangkau), BUKAN hasil kejadian.
Hasil kejadian tetap hanya dari laporan KoboToolbox lewat 16 -> 17 -> 20, sehingga penilaian prospektif (18) tidak berubah.
Tiap PATCH menambah satu baris berisi keadaan lengkap; tidak ada UPDATE atau DELETE (dijaga trigger), supaya riwayat dan
dua waktunya (dikunjungi_pada = kapan berlaku, dicatat_pada = kapan masuk sistem) bisa diaudit.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

STATUS = ("belum", "dalam_perjalanan", "diperiksa", "tidak_terjangkau")
NEEDS_VISIT_TIME = ("diperiksa", "tidak_terjangkau")
COLS = ("id_tugas", "issue_date", "status", "catatan", "dikunjungi_pada", "dicatat_pada")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS task_update (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id_tugas TEXT NOT NULL,
    issue_date TEXT NOT NULL,
    status TEXT NOT NULL,
    catatan TEXT,
    dikunjungi_pada TEXT,
    dicatat_pada TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_task ON task_update (id_tugas, seq);
CREATE TRIGGER IF NOT EXISTS no_update BEFORE UPDATE ON task_update BEGIN SELECT RAISE(ABORT, 'task_update hanya boleh ditambah'); END;
CREATE TRIGGER IF NOT EXISTS no_delete BEFORE DELETE ON task_update BEGIN SELECT RAISE(ABORT, 'task_update hanya boleh ditambah'); END;
"""


class TaskUpdates:
    """Akses tambah-saja ke riwayat status tugas."""

    def __init__(self, db: Path):
        self.db = Path(db)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        """Koneksi singkat: commit bila lancar, rollback bila galat, selalu ditutup."""
        self.db.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.db)
        try:
            con.executescript(_SCHEMA)
            with con:
                yield con
        finally:
            con.close()

    def add(self, id_tugas: str, issue_date: str, status: str, catatan: str | None, dikunjungi_pada: str | None) -> dict:
        """Tambah satu keadaan lengkap. Validasi isi dilakukan pemanggil (api/app.py)."""
        if status not in STATUS:
            raise ValueError(f"status harus salah satu dari {STATUS}")
        row = (id_tugas, issue_date, status, catatan, dikunjungi_pada, datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
        with self._conn() as con:
            con.execute(f"INSERT INTO task_update ({', '.join(COLS)}) VALUES (?, ?, ?, ?, ?, ?)", row)
        return dict(zip(COLS, row))

    def latest(self) -> dict[str, dict]:
        """Keadaan terakhir per tugas. Kosong bila basis data belum ada (tidak membuat berkas)."""
        if not self.db.exists():
            return {}
        with self._conn() as con:
            rows = con.execute(f"SELECT {', '.join(COLS)} FROM task_update t WHERE seq = "
                               "(SELECT MAX(seq) FROM task_update WHERE id_tugas = t.id_tugas)").fetchall()
        return {r[0]: dict(zip(COLS, r)) for r in rows}

    def history(self, id_tugas: str) -> list[dict]:
        if not self.db.exists():
            return []
        with self._conn() as con:
            rows = con.execute(f"SELECT {', '.join(COLS)} FROM task_update WHERE id_tugas = ? ORDER BY seq", (id_tugas,)).fetchall()
        return [dict(zip(COLS, r)) for r in rows]
