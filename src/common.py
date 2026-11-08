"""Fungsi bersama: memuat konfigurasi dan jalur proyek."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_config() -> dict:
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def path(key: str) -> Path:
    """Ambil jalur folder dari config, buat jika belum ada."""
    p = ROOT / load_config()["paths"][key]
    p.mkdir(parents=True, exist_ok=True)
    return p
