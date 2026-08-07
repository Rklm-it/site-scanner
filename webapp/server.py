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

from scanner import analytics, enrich, mirror, outreach, pipeline
from scanner.catalog import CATALOG
from scanner.config import Settings
from scanner.report import write_csv, write_json

import re

from . import mailer, screenshot, secrets_store
from .leads_store import STATUSES, TRASH, LeadStore

DATA_DIR = Path(os.environ.get("SCANNER_DATA", "webapp_data"))
JOBS_DIR = DATA_DIR / "jobs"
SHOTS_DIR = DATA_DIR / "shots"
DUMPS_DIR = DATA_DIR / "dumps"
STATIC = Path(__file__).parent / "static"
_DOMAIN_RE = re.compile(r"^[a-z0-9.\-]+$", re.I)
# Имя архива приходит из URL — пускаем только то, что сами же и сгенерировали,
# иначе «../» в имени увела бы отдачу файла за пределы папки выгрузок.
_ARCHIVE_RE = re.compile(r"^[a-z0-9.\-]+-\d{4}-\d{2}-\d{2}-\d{4}\.zip$", re.I)

# Чтобы логи движка (scanner.*) были видны в docker compose logs.
# ВАЖНО: одного setLevel мало. Свой обработчик тут не настроен, uvicorn
# настраивает только свои логгеры, и сообщения уходили в аварийный обработчик
# logging.lastResort — а он пропускает лишь WARNING и выше. В итоге весь
# INFO-разбор прогона («выдача N → к скану M», «К сканированию: N доменов»)
# в логи не попадал вообще, и диагностировать пустой скан было нечем.
_scan_log = logging.getLogger("scanner")
_scan_log.setLevel(logging.INFO)
if not _scan_log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))
    _scan_log.addHandler(_h)

STORE: LeadStore | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global STORE
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    DUMPS_DIR.mkdir(parents=True, exist_ok=True)
    STORE = LeadStore(str(DATA_DIR / "leads.sqlite"))
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
    collect_done: int = 0
    collect_total: int = 0
    phase: str = ""                  # collect / scan / enrich / rank
    enrich_done: int = 0
    enrich_total: int = 0
    started: float = field(default_factory=time.time)
    finished: float | None = None

    def public(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "phase": self.phase,
            "done": self.done,
            "total": self.total,
            "collect_done": self.collect_done,
            "collect_total": self.collect_total,
            "enrich_done": self.enrich_done,
            "enrich_total": self.enrich_total,
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
    concurrency: int = 16
    timeout: float = 8.0
    per_host_delay: float = 0.5
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
        skip_domains=trash_domains(),
        out=out_base,
    )


def trash_domains() -> list[str]:
    """Домены, помеченные в базе как мусор — их не собираем заново."""
    if not STORE:
        return []
    return [d for d, st in STORE.all().items() if st.get("status") == TRASH]


def compose_signature() -> str:
    """Подпись для писем из настроек: имя + контакты + портфолио."""
    name = os.environ.get("SMTP_FROM_NAME", "").strip() or "[Ваше имя]"
    contact = os.environ.get("SENDER_CONTACT", "").strip() or "[телефон / телеграм]"
    lines = [name, contact]
    portfolio = os.environ.get("PORTFOLIO_URL", "").strip()
    if portfolio:
        lines.append(portfolio)
    return "\n".join(lines)


class _WarnCollector(logging.Handler):
    """Складывает WARNING-логи скана в job.warnings — чтобы ошибки провайдера
    (например «Yandex 403») были видны в интерфейсе, а не только в docker logs."""

    def __init__(self, job: "Job") -> None:
        super().__init__(level=logging.WARNING)
        self.job = job

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage().strip().replace("\n", " ")
        except Exception:  # noqa: BLE001
            return
        if len(msg) > 220:
            msg = msg[:220] + "…"
        if msg and msg not in self.job.warnings and len(self.job.warnings) < 25:
            self.job.warnings.append(msg)


def _run_job(job: Job, settings: Settings) -> None:
    job.status = "running"

    def progress(done: int, total: int) -> None:
        job.done = done
        job.total = total

    def on_collect(done: int, total: int) -> None:
        job.collect_done = done
        job.collect_total = total

    def on_phase(name: str) -> None:
        job.phase = name

    def on_enrich(done: int, total: int) -> None:
        job.enrich_done = done
        job.enrich_total = total

    scan_log = logging.getLogger("scanner")
    handler = _WarnCollector(job)
    scan_log.addHandler(handler)
    try:
        leads = pipeline.run(settings, progress=progress, on_collect=on_collect,
                             on_phase=on_phase, on_enrich=on_enrich)
        analytics.annotate(leads)  # идемпотентно; гарантирует поля приоритета
        Path(settings.out).parent.mkdir(parents=True, exist_ok=True)
        write_csv(leads, settings.out + ".csv")
        write_json(leads, settings.out + ".json")

        saved = STORE.all() if STORE else {}
        signature = compose_signature()
        caller = os.environ.get("SMTP_FROM_NAME", "").strip()
        about = os.environ.get("STUDIO_ABOUT", "").strip() or None
        rows = []
        for l in leads:
            row = l.to_row()
            row.update(outreach.build_message(l, signature=signature, about=about))
            row["call_script"] = outreach.build_call_script(l, caller_name=caller, about=about)
            tp = outreach.build_talking_points(l)
            row["talk_savvy"] = tp["savvy"]
            row["talk_simple"] = tp["simple"]
            row["lovable_brief"] = outreach.build_lovable_brief(l)
            st = saved.get(l.domain, {})
            row["status"] = st.get("status", "")
            row["note"] = st.get("note", "")
            row["callback"] = st.get("callback", "")
            row["mrr"] = st.get("mrr", 0)
            row["prototype_url"] = st.get("prototype_url", "")
            rows.append(row)
        job.leads = rows
        if STORE:
            STORE.upsert_leads(rows)      # копим в базу просканированных
        job.summary = analytics.summarize(leads)
        job.status = "done"
    except Exception as exc:  # noqa: BLE001
        job.status = "error"
        job.error = f"{type(exc).__name__}: {exc}"
    finally:
        scan_log.removeHandler(handler)
        job.phase = ""
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
        "secrets": secrets_store.api_key_status(),
        "smtp": secrets_store.smtp_values(),
        "providers": ["yandex", "google", "serpapi_google", "serpapi_yandex", "duckduckgo"],
        "categories_catalog": CATALOG,
        "statuses": list(STATUSES),        # чтобы список не дублировался в JS
        "defaults": ScanRequest().model_dump(),
    }


@app.post("/api/secrets")
def save_secrets(values: dict[str, str]) -> dict:
    secrets_store.save(values)
    return {"ok": True, "secrets": secrets_store.api_key_status()}


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


# --- статусы лидов (мини-CRM) ---
class LeadStateUpdate(BaseModel):
    domain: str
    status: str | None = None
    note: str | None = None
    callback: str | None = None
    deal_amount: float | None = None
    mrr: float | None = None
    prototype_url: str | None = None


@app.get("/api/base")
def leads_base() -> dict:
    leads = STORE.all_leads() if STORE else []
    return {"count": len(leads), "leads": leads}


@app.get("/api/screenshot/{domain}")
def screenshot_of(domain: str):
    """Ленивый скриншот главной страницы лида (кэшируется на диск)."""
    if not _DOMAIN_RE.match(domain):
        raise HTTPException(400, "Некорректный домен.")
    path = SHOTS_DIR / f"{domain}.png"
    if not path.exists():
        url = None
        if STORE:
            for l in STORE.all_leads():
                if l.get("domain") == domain:
                    url = l.get("url") or f"https://{domain}"
                    break
        url = url or f"https://{domain}"
        try:
            screenshot.capture(url, path)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(502, f"Не удалось снять скриншот: {exc}")
    return FileResponse(path, media_type="image/png")


class RevenueReq(BaseModel):
    domain: str = ""
    inn: str | None = None
    ogrn: str | None = None
    company: str | None = None


@app.post("/api/revenue")
def revenue_check(req: RevenueReq) -> dict:
    """Проверка оборота/статуса компании: по ИНН со страницы или по названию.

    Данные лида принимаются напрямую от клиента (работает даже если скан
    ещё не сохранён в базу); при их отсутствии — фолбэк на базу по домену.
    """
    if not (os.environ.get("DADATA_TOKEN") or os.environ.get("DATANEWTON_TOKEN")):
        raise HTTPException(400, "Не задан ключ DaData или DataNewton (панель «API-ключи»).")

    inn = (req.inn or "").strip() or None
    ogrn = (req.ogrn or "").strip() or None
    name = (req.company or "").strip() or None
    if not inn and not ogrn and not name and req.domain and STORE:
        lead = next((l for l in STORE.all_leads() if l.get("domain") == req.domain), None)
        if lead:
            inn = lead.get("inn") or None
            ogrn = lead.get("ogrn") or None
            name = (lead.get("company") or "").strip() or None
    if not inn and not ogrn and not name:
        raise HTTPException(422, "Нет ни ИНН/ОГРН, ни названия компании — не по чему искать.")

    e, err = enrich.lookup_verbose(inn=inn, name=name, ogrn=ogrn)
    found = bool(e.official_name or e.revenue is not None)
    # Разные причины пустого оборота — это не ошибка ключа, а особенность
    # компании. Формулировка общая со сканом, чтобы ручная проверка и таблица
    # не объясняли одно и то же разными словами.
    err = err or e.note
    return {
        "found": found,
        "official_name": e.official_name, "status": e.status, "revenue": e.revenue,
        "employee_count": e.employee_count, "management": e.management,
        "address": e.address, "registration_date": e.registration_date,
        "is_individual": e.is_individual,
        "inn": e.inn or inn or "",
        "error": err,
    }


@app.get("/api/leads/state")
def leads_state() -> dict:
    return STORE.all() if STORE else {}


@app.post("/api/leads/state")
def set_lead_state(upd: LeadStateUpdate) -> dict:
    if not STORE:
        raise HTTPException(503, "Хранилище не готово.")
    if upd.status is not None and upd.status not in STATUSES:
        raise HTTPException(400, f"Недопустимый статус. Допустимо: {', '.join(s for s in STATUSES if s)}")
    return {"domain": upd.domain,
            **STORE.set(upd.domain, status=upd.status, note=upd.note, callback=upd.callback,
                        deal_amount=upd.deal_amount, mrr=upd.mrr, prototype_url=upd.prototype_url)}


# --- рассылка писем через SMTP собственного ящика ---
class SendOne(BaseModel):
    domain: str
    to: str
    subject: str
    body: str


class SendBulk(BaseModel):
    domains: list[str]
    delay: float = mailer.DEFAULT_DELAY


@app.get("/api/smtp")
def smtp_info() -> dict:
    return secrets_store.smtp_values()


@app.post("/api/send/test")
def send_test() -> dict:
    cfg = mailer.smtp_config()
    if not mailer.is_configured():
        raise HTTPException(400, "SMTP не настроен.")
    try:
        mailer.send_email(cfg["user"], "site-scanner: проверка отправки",
                          "Это тестовое письмо из site-scanner. Если вы его получили — SMTP работает.")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Ошибка отправки: {exc}")
    return {"ok": True, "to": cfg["user"]}


@app.post("/api/send")
def send_one(req: SendOne) -> dict:
    if not mailer.is_configured():
        raise HTTPException(400, "SMTP не настроен.")
    if not req.to or "@" not in req.to:
        raise HTTPException(400, "У этого лида нет корректной почты.")
    try:
        mailer.send_email(req.to, req.subject, req.body)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Ошибка отправки: {exc}")
    if STORE:
        STORE.set(req.domain, status="написал")
    return {"ok": True}


@dataclass
class SendJob:
    id: str
    total: int = 0
    sent: int = 0
    failed: int = 0
    done: bool = False
    errors: list[str] = field(default_factory=list)

    def public(self) -> dict:
        return {"id": self.id, "total": self.total, "sent": self.sent,
                "failed": self.failed, "done": self.done, "errors": self.errors[:10]}


SEND_JOBS: dict[str, SendJob] = {}


def _run_send(job: SendJob, targets: list[tuple[str, str, str, str]], delay: float) -> None:
    for i, (domain, to, subject, body) in enumerate(targets):
        try:
            mailer.send_email(to, subject, body)
            job.sent += 1
            if STORE:
                STORE.set(domain, status="написал")
        except Exception as exc:  # noqa: BLE001
            job.failed += 1
            job.errors.append(f"{domain}: {exc}")
        if i < len(targets) - 1:
            time.sleep(delay)
    job.done = True


@app.post("/api/send/bulk")
def send_bulk(req: SendBulk) -> dict:
    if not mailer.is_configured():
        raise HTTPException(400, "SMTP не настроен.")
    if not STORE:
        raise HTTPException(503, "Хранилище не готово.")

    by_domain = {l["domain"]: l for l in STORE.all_leads()}
    targets: list[tuple[str, str, str, str]] = []
    for domain in req.domains[:mailer.DEFAULT_DAILY_CAP]:
        lead = by_domain.get(domain)
        if not lead:
            continue
        to = (lead.get("emails") or "").split(",")[0].strip()
        if not to or "@" not in to:
            continue
        targets.append((domain, to, lead.get("pitch_subject") or "", lead.get("pitch_body") or ""))

    if not targets:
        raise HTTPException(400, "Некому слать: нет лидов с почтой в выборке.")

    sid = uuid.uuid4().hex[:12]
    job = SendJob(id=sid, total=len(targets))
    SEND_JOBS[sid] = job
    delay = max(5.0, float(req.delay))
    threading.Thread(target=_run_send, args=(job, targets, delay), daemon=True).start()
    capped = len(req.domains) > mailer.DEFAULT_DAILY_CAP
    return {"send_id": sid, "total": len(targets), "capped": capped, "cap": mailer.DEFAULT_DAILY_CAP}


@app.get("/api/send/{send_id}")
def send_status(send_id: str) -> dict:
    job = SEND_JOBS.get(send_id)
    if not job:
        raise HTTPException(404, "Рассылка не найдена.")
    return job.public()


# --------------------------------------------------------------------------- #
# Выгрузка сайта клиента целиком
#
# Раньше это делалось руками на сервере через wget, а архив перекладывался в
# репозиторий. Теперь кнопкой: выгрузка идёт тем же движком, что и скан, и
# ложится готовым zip-архивом в список — его остаётся только скачать.
# --------------------------------------------------------------------------- #
class DumpRequest(BaseModel):
    domain: str
    max_pages: int = 150
    max_depth: int = 3
    respect_robots: bool = True


@dataclass
class DumpJob:
    id: str
    domain: str
    status: str = "running"          # running / done / error
    pages: int = 0
    assets: int = 0
    bytes: int = 0
    archive: str | None = None
    archive_bytes: int = 0
    stopped_by: str | None = None
    error: str | None = None
    errors: list[str] = field(default_factory=list)
    started: float = field(default_factory=time.time)

    def public(self) -> dict:
        return {
            "id": self.id, "domain": self.domain, "status": self.status,
            "pages": self.pages, "assets": self.assets, "bytes": self.bytes,
            "archive": self.archive, "archive_bytes": self.archive_bytes,
            "stopped_by": self.stopped_by, "error": self.error,
            "errors": self.errors[:10],
            "elapsed": round(time.time() - self.started, 1),
        }


DUMP_JOBS: dict[str, DumpJob] = {}


def _run_dump(job: DumpJob, req: DumpRequest) -> None:
    work = DUMPS_DIR / f".work-{job.id}"
    try:
        def on_progress(st: mirror.MirrorStats) -> None:
            job.pages, job.assets, job.bytes = st.pages, st.assets, st.bytes

        stats = mirror.run(
            job.domain, work,
            max_pages=max(1, min(req.max_pages, 600)),
            max_depth=max(1, min(req.max_depth, 6)),
            respect_robots=req.respect_robots,
            on_progress=on_progress,
        )
        job.pages, job.assets, job.bytes = stats.pages, stats.assets, stats.bytes
        job.stopped_by = stats.stopped_by
        job.errors = stats.errors
        if not stats.pages:
            raise RuntimeError(
                "не удалось скачать ни одной страницы — сайт недоступен "
                "или закрыт в robots.txt (снимите галочку)"
            )
        name = f"{job.domain}-{time.strftime('%Y-%m-%d-%H%M')}.zip"
        job.archive_bytes = mirror.pack(work, DUMPS_DIR / name)
        job.archive = name
        job.status = "done"
    except Exception as exc:  # noqa: BLE001
        job.status = "error"
        job.error = f"{type(exc).__name__}: {exc}"
        # Недокачанное не оставляем на томе: место на сервере не бесконечное,
        # а повторный запуск всё равно начинает с нуля.
        if work.exists():
            for p in sorted(work.rglob("*"), reverse=True):
                p.rmdir() if p.is_dir() else p.unlink()
            work.rmdir()


@app.post("/api/dump")
def start_dump(req: DumpRequest) -> dict:
    domain = (req.domain or "").strip().lower()
    for prefix in ("https://", "http://"):
        domain = domain.removeprefix(prefix)
    domain = domain.split("/")[0].strip(".")
    if not domain or not _DOMAIN_RE.match(domain) or "." not in domain:
        raise HTTPException(400, "Укажите домен вида example.ru")
    if any(j.status == "running" for j in DUMP_JOBS.values()):
        raise HTTPException(409, "Одна выгрузка уже идёт — дождитесь её окончания.")
    job = DumpJob(id=uuid.uuid4().hex[:12], domain=domain)
    DUMP_JOBS[job.id] = job
    threading.Thread(target=_run_dump, args=(job, req), daemon=True).start()
    return {"dump_id": job.id}


@app.get("/api/dump/{dump_id}")
def dump_status(dump_id: str) -> dict:
    job = DUMP_JOBS.get(dump_id)
    if not job:
        raise HTTPException(404, "Выгрузка не найдена.")
    return job.public()


@app.get("/api/dumps")
def list_dumps() -> dict:
    """Список готовых архивов.

    Читается с диска, а не из памяти процесса: задачи перезапуск контейнера не
    переживают (известное ограничение), а вот уже собранные архивы лежат на
    томе и теряться не должны.
    """
    DUMPS_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for path in DUMPS_DIR.glob("*.zip"):
        st = path.stat()
        items.append({
            "name": path.name,
            "domain": path.name.rsplit("-", 4)[0],
            "bytes": st.st_size,
            "created": time.strftime("%d.%m.%Y %H:%M", time.localtime(st.st_mtime)),
            "mtime": st.st_mtime,
        })
    items.sort(key=lambda i: i["mtime"], reverse=True)
    return {"count": len(items), "dumps": items}


@app.get("/api/dumps/{name}")
def download_dump(name: str):
    if not _ARCHIVE_RE.match(name):
        raise HTTPException(400, "Некорректное имя архива.")
    path = DUMPS_DIR / name
    if not path.exists():
        raise HTTPException(404, "Архив не найден.")
    return FileResponse(path, media_type="application/zip", filename=name)


@app.delete("/api/dumps/{name}")
def delete_dump(name: str) -> dict:
    if not _ARCHIVE_RE.match(name):
        raise HTTPException(400, "Некорректное имя архива.")
    path = DUMPS_DIR / name
    if not path.exists():
        raise HTTPException(404, "Архив не найден.")
    path.unlink()
    return {"ok": True}
