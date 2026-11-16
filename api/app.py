"""API v1 peringatan dini kekeringan gambut: GET untuk semua sumber daya, PATCH hanya untuk status lapangan tugas.

    uvicorn api.app:create_app --factory --port 8000          # API di /v1, dokumentasi di /docs, web di /
    PEAT_API_TOKEN=rahasia uvicorn api.app:create_app --factory   # menghidupkan PATCH (tanpa token: tulis nonaktif)

Membaca webmap/data hasil 09, 10, dan 20 tanpa menghitung ulang. Skema dan contoh: docs/API.md.
"""
from __future__ import annotations

import os
import re
import secrets
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from src.api_store import BadRequest, DataStore, MissingData, NotFound
from src.task_updates import NEEDS_VISIT_TIME, STATUS, TaskUpdates

ROOT = Path(__file__).resolve().parents[1]
WIB = timezone(timedelta(hours=7))
GEOJSON = "application/geo+json"
SAFE_ID = re.compile(r"^[A-Za-z0-9_.\-]{1,80}$")


class TaskPatch(BaseModel):
    """Isi PATCH tugas. Kolom yang tidak dikirim mempertahankan nilai terakhir."""

    model_config = ConfigDict(extra="forbid")
    status: Literal[STATUS] | None = None  # type: ignore[valid-type]
    catatan: str | None = Field(None, max_length=280, description="Jangan menulis nama orang.")
    dikunjungi_pada: datetime | None = Field(None, description="Waktu kunjungan ISO 8601 dengan zona waktu, wajib untuk diperiksa dan tidak_terjangkau.")


def _err(status: int, code: str, description: str) -> JSONResponse:
    return JSONResponse({"code": code, "description": description}, status_code=status)


def create_app(data_dir: Path | None = None, db_path: Path | None = None, web_dir: Path | None = None,
               token: str | None = None) -> FastAPI:
    """Bangun aplikasi. Argumen kosong mengikuti tata letak proyek dan variabel lingkungan PEAT_API_TOKEN, PEAT_API_CORS."""
    if db_path is None:
        from src.common import path
        db_path = path("interim") / "task_updates.sqlite"
    web_dir = web_dir or ROOT / "webmap"
    data_dir = data_dir or web_dir / "data"
    token = token if token is not None else os.environ.get("PEAT_API_TOKEN", "")
    tasks_db = TaskUpdates(db_path)
    store = DataStore(data_dir, task_status=tasks_db.latest)

    app = FastAPI(title="Peat early warning API", version="1", description="Baca-saja kecuali status lapangan tugas. Lihat docs/API.md.")
    origins = [o for o in os.environ.get("PEAT_API_CORS", "").split(",") if o]
    if origins:
        app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "PATCH"], allow_headers=["Authorization", "Content-Type"])

    @app.exception_handler(MissingData)
    async def _missing(_: Request, e: MissingData):
        return _err(503, "data_belum_ada", str(e))

    @app.exception_handler(NotFound)
    async def _nf(_: Request, e: NotFound):
        return _err(404, "tidak_ditemukan", str(e))

    @app.exception_handler(BadRequest)
    async def _bad(_: Request, e: BadRequest):
        return _err(400, "parameter_tidak_sah", str(e))

    @app.exception_handler(RequestValidationError)
    async def _invalid(_: Request, e: RequestValidationError):
        return _err(400, "parameter_tidak_sah", "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors()))

    def geo(obj: dict) -> JSONResponse:
        return JSONResponse(obj, media_type=GEOJSON)

    @app.get("/v1", tags=["umum"])
    def landing():
        return {"title": app.title, "links": [{"rel": r, "href": h} for r, h in (
            ("service-doc", "/docs"), ("service-desc", "/openapi.json"), ("data", "/v1/collections"), ("meta", "/v1/meta"))]}

    @app.get("/v1/meta", tags=["umum"])
    def meta():
        return store.meta()

    @app.get("/v1/collections", tags=["koleksi"])
    def collections():
        return store.collections()

    @app.get("/v1/collections/{cid}", tags=["koleksi"])
    def collection(cid: str):
        hit = next((c for c in store.collections()["collections"] if c["id"] == cid), None)
        if hit is None:
            raise NotFound(f"koleksi '{cid}' tidak ada")
        return hit

    @app.get("/v1/collections/{cid}/items", tags=["koleksi"], response_class=JSONResponse)
    def items(cid: str, request: Request):
        """Penyaring: limit, offset, bbox, dan queryables tiap koleksi (lihat /v1/collections)."""
        return geo(store.query(cid, dict(request.query_params)))

    @app.get("/v1/collections/{cid}/items/{fid}", tags=["koleksi"])
    def item(cid: str, fid: str):
        return geo(store.item(cid, fid))

    @app.patch("/v1/collections/tasks/items/{fid}", tags=["tugas"])
    def patch_task(fid: str, body: TaskPatch, authorization: str = Header("")):
        if not token:
            return _err(403, "tulis_nonaktif", "PATCH nonaktif: server dijalankan tanpa PEAT_API_TOKEN.")
        if not secrets.compare_digest(authorization.encode(), f"Bearer {token}".encode()):
            return _err(401, "tidak_berwenang", "Sertakan header Authorization: Bearer <token>.")
        if not body.model_fields_set:
            raise BadRequest("kirim paling sedikit satu kolom: status, catatan, atau dikunjungi_pada")
        feat = store.item("tasks", fid)
        issue = store.features("tasks")[1]["issue_date"]
        prev = tasks_db.latest().get(fid, {})
        status = body.status or prev.get("status", "belum")
        visit = body.dikunjungi_pada
        if visit is not None:
            if visit.tzinfo is None:
                raise BadRequest("dikunjungi_pada harus memuat zona waktu, misalnya 2026-11-16T09:30:00+07:00")
            if visit.astimezone(WIB).date() < date.fromisoformat(issue):
                raise BadRequest(f"dikunjungi_pada lebih awal dari tanggal terbit tugas ({issue})")
            if visit > datetime.now(UTC) + timedelta(minutes=5):
                raise BadRequest("dikunjungi_pada tidak boleh di masa depan")
        visit_s = visit.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if visit else prev.get("dikunjungi_pada")
        if status in NEEDS_VISIT_TIME and not visit_s:
            raise BadRequest(f"status '{status}' wajib disertai dikunjungi_pada")
        catatan = body.catatan if "catatan" in body.model_fields_set else prev.get("catatan")
        tasks_db.add(fid, issue, status, catatan, visit_s)
        return geo(store.item("tasks", feat["id"]))

    @app.get("/v1/collections/tasks/items/{fid}/history", tags=["tugas"])
    def task_history(fid: str):
        store.item("tasks", fid)
        return {"id_tugas": fid, "history": tasks_db.history(fid)}

    @app.get("/v1/stations/{sid}/series", tags=["monitoring"])
    def series(sid: str, days: int | None = Query(None, ge=1, le=3650)):
        if not SAFE_ID.match(sid):
            raise NotFound(f"stasiun '{sid}' tidak ada")
        return store.series(sid, days)

    @app.get("/v1/susceptibility", tags=["monitoring"])
    def susceptibility():
        return store.susceptibility()

    @app.get("/v1/layers", tags=["monitoring"])
    def layers():
        return store.layers()

    @app.get("/v1/validation", tags=["prediksi"])
    def validation():
        return store.validation()

    @app.get("/v1/scores", tags=["respons"])
    def scores():
        return store.scores()

    if (web_dir / "index.html").exists():
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
    return app
