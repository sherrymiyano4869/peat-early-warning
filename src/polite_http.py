"""Klien HTTP sopan untuk mengambil data publik dengan jeda, retry, dan cache.

Pakai untuk endpoint JSON yang ditemukan lewat DevTools. Jangan dipakai untuk
melewati login, CAPTCHA, atau pembatasan akses.
"""
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests


class PoliteClient:
    def __init__(
        self,
        cache_dir,
        min_interval: float = 1.5,
        user_agent: str = "AGC2027-peat-research (kontak: ISI-EMAIL-KAMU)",
        timeout: int = 30,
        max_retries: int = 3,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_interval = min_interval
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept": "application/json"})
        self._last_request = 0.0

    def _wait(self) -> None:
        gap = time.monotonic() - self._last_request
        if gap < self.min_interval:
            time.sleep(self.min_interval - gap)
        self._last_request = time.monotonic()

    def _cache_path(self, url: str, params, name=None) -> Path:
        if name:  # nama berkas yang mudah dibaca, misalnya id stasiun
            return self.cache_dir / f"{name}.json"
        raw = url + json.dumps(params or {}, sort_keys=True)
        return self.cache_dir / (hashlib.sha256(raw.encode()).hexdigest()[:24] + ".json")

    def get_json(self, url: str, params=None, force: bool = False, name=None):
        """Ambil JSON dari cache bila ada; jika tidak, unduh dengan jeda dan retry."""
        path = self._cache_path(url, params, name)
        if path.exists() and not force:
            return json.loads(path.read_text(encoding="utf-8"))["data"]

        for attempt in range(self.max_retries):
            self._wait()
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException:
                time.sleep(2 ** attempt)
                continue
            if resp.status_code == 429 or resp.status_code >= 500:
                wait = float(resp.headers.get("Retry-After", 2 ** (attempt + 1)))
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            record = {
                "url": resp.url,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "data": data,
            }
            path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            return data
        raise RuntimeError(f"Gagal mengambil {url} setelah {self.max_retries} percobaan")
