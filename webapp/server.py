"""FastAPI-бэкенд веб-интерфейса site-scanner."""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from scanner import analytics, pipeline
from scanner.catalog import CATALOG
from scanner.config import Settings
from scanner.report import write_csv, write_json

from . import secrets_store

DATA_DIR = Path(os.environ.get("SCANNER_DATA", "webapp_data"))
JOBS_DIR = DATA_DIR / "jobs"
STATIC = Path(__file__).parent / "static"

# Чтобы INFO-логи движка (scanner.*) были видны в docker compose logs
logging.getLogger("scanner").setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    secrets_store.load_into_env()
    yield


app = FastAPI(title="site-scanner", lifespan=lifespan)


# --------------------------------------------------------------------------- #
# Реестр задач
# --------------------------------------------------------------------------- #
@dataclass
class Job:
    id: str
    status: str = "queued"           # queued / running / done / error
    done: int = 0
    total: int | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    leads: list[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    started: float = field(default_factory=time.time)
    finished: float | None = None

    def public(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "done": self.done,
            "total": self.total,
            "error": self.error,
            "warnings": self.warnings,
            "count": len(self.leads),
            "leads": self.leads,
            "summary": self.summary,
            "elapsed": round((self.finished or time.time()) - self.started, 1),
        }


JOBS: dict[str, Job] = {}
_LOCK = threading.Lock()


# --------------------------------------------------------------------------- #
# Модель запроса на скан
# --------------------------------------------------------------------------- #
class ScanRequest(BaseModel):
    queries: str = ""
    categories: str = ""
    cities: str = ""
    providers: list[str] = ["yandex", "google"]
    max_per_query: int = 20
    min_score: int = 30
    concurrency: int = 8
    timeout: float = 12.0
    per_host_delay: float = 1.0
    respect_robots: bool = True
    follow_contact_page: bool = True
    enrich: bool = False
    skip_seen: bool = False
    use_cache: bool = True


def _split(text: str) -> list[str]:
    items: list[str] = []
    for line in (text or "").replace(",", "\n").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            items.append(line)
    return items


def _credential_warnings(req: ScanRequest) -> list[str]:
    warns: list[str] = []
    env = os.environ.get
    for p in req.providers:
        if p == "yandex" and not ((env("YANDEX_API_KEY") and env("YANDEX_FOLDER_ID"))
                                  or (env("YANDEX_XML_USER") and env("YANDEX_XML_KEY"))):
            warns.append("Яндекс: не заданы ключи — провайдер вернёт пусто.")
        if p == "google" and not (env("GOOGLE_API_KEY") and env("GOOGLE_CSE_CX")):
            warns.append("Google: не заданы GOOGLE_API_KEY / GOOGLE_CSE_CX.")
        if p in ("serpapi_google", "serpapi_yandex") and not env("SERPAPI_KEY"):
            warns.append("SerpAPI: не задан SERPAPI_KEY.")
    if req.enrich and not env("DADATA_TOKEN"):
        warns.append("Обогащение по ИНН: не задан DADATA_TOKEN.")
    return warns


def _build_settings(req: ScanRequest, job_id: str) -> Settings:
    out_base = str(JOBS_DIR / job_id / "leads")
    return Settings(
        queries=_split(req.queries),
        categories=_split(req.categories),
        cities=_split(req.cities),
        providers=req.providers or ["yandex", "google"],
        max_per_query=req.max_per_query,
        min_score=req.min_score,
        concurrency=req.concurrency,
        timeout=req.timeout,
        per_host_delay=req.per_host_delay,
        respect_robots=req.respect_robots,
        follow_contact_page=req.follow_contact_page,
        enrich=req.enrich,
        skip_seen=req.skip_seen,
        cache_path=str(DATA_DIR / "cache.sqlite") if req.use_cache else None,
        out=out_base,
    )


def _run_job(job: Job, settings: Settings) -> None:
    job.status = "running"

    def progress(done: int, total: int) -> None:
        job.done = done
        job.total = total

    try:
        leads = pipeline.run(settings, progress=progress)
        analytics.annotate(leads)  # идемпотентно; гарантирует поля приоритета
        Path(settings.out).parent.mkdir(parents=True, exist_ok=True)
        write_csv(leads, settings.out + ".csv")
        write_json(leads, settings.out + ".json")
        job.leads = [l.to_row() for l in leads]
        job.summary = analytics.summarize(leads)
        job.status = "done"
    except Exception as exc:  # noqa: BLE001
        job.status = "error"
        job.error = f"{type(exc).__name__}: {exc}"
    finally:
        job.finished = time.time()


# --------------------------------------------------------------------------- #
# Эндпоинты
# --------------------------------------------------------------------------- #
@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((STATIC / "index.html").read_text(encoding="utf-8"))


@app.get("/api/config")
def get_config() -> dict:
    return {
        "secrets": secrets_store.status(),
        "providers": ["yandex", "google", "serpapi_google", "serpapi_yandex", "duckduckgo"],
        "categories_catalog": CATALOG,
        "defaults": ScanRequest().model_dump(),
    }


@app.post("/api/secrets")
def save_secrets(values: dict[str, str]) -> dict:
    secrets_store.save(values)
    return {"ok": True, "secrets": secrets_store.status()}


@app.post("/api/scan")
def start_scan(req: ScanRequest) -> dict:
    if not (_split(req.queries) or _split(req.categories)):
        raise HTTPException(400, "Задайте хотя бы один запрос или категорию.")
    job_id = uuid.uuid4().hex[:12]
    job = Job(id=job_id, warnings=_credential_warnings(req))
    with _LOCK:
        JOBS[job_id] = job
    settings = _build_settings(req, job_id)
    threading.Thread(target=_run_job, args=(job, settings), daemon=True).start()
    return {"job_id": job_id, "warnings": job.warnings}


@app.get("/api/scan/{job_id}")
def scan_status(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Задача не найдена.")
    return job.public()


@app.get("/api/scan/{job_id}/export.{fmt}")
def export(job_id: str, fmt: str):
    if job_id not in JOBS:
        raise HTTPException(404, "Задача не найдена.")
    if fmt not in ("csv", "json"):
        raise HTTPException(400, "Формат: csv или json.")
    path = JOBS_DIR / job_id / f"leads.{fmt}"
    if not path.exists():
        raise HTTPException(404, "Файл ещё не готов.")
    media = "text/csv" if fmt == "csv" else "application/json"
    return FileResponse(path, media_type=media, filename=f"leads-{job_id}.{fmt}")
