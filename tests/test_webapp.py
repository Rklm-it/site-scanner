"""Тесты веб-API (FastAPI TestClient, без сети)."""

import time

import pytest
from fastapi.testclient import TestClient

from scanner.models import Lead, Contacts, Enrichment


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from webapp import server, secrets_store

    monkeypatch.setattr(server, "DATA_DIR", tmp_path)
    monkeypatch.setattr(server, "JOBS_DIR", tmp_path / "jobs")
    monkeypatch.setattr(server, "SHOTS_DIR", tmp_path / "shots")
    monkeypatch.setattr(server, "DUMPS_DIR", tmp_path / "dumps")
    monkeypatch.setattr(secrets_store, "_PATH", tmp_path / "secrets.local.json")
    for env in secrets_store.FIELDS.values():
        monkeypatch.delenv(env, raising=False)

    with TestClient(server.app) as c:
        yield c, server


def test_config_endpoint(client):
    c, _ = client
    cfg = c.get("/api/config").json()
    assert "yandex" in cfg["providers"] and "google" in cfg["providers"]
    assert cfg["secrets"]["google_api_key"] is False
    assert "defaults" in cfg
    assert "Авто" in cfg["categories_catalog"]
    assert "автосервис" in cfg["categories_catalog"]["Авто"]


def test_secrets_save_and_status(client):
    c, _ = client
    r = c.post("/api/secrets", json={"google_api_key": "AIza-test", "google_cse_cx": "cx1"}).json()
    assert r["ok"] and r["secrets"]["google_api_key"] is True
    assert c.get("/api/config").json()["secrets"]["google_cse_cx"] is True


def test_scan_requires_query(client):
    c, _ = client
    assert c.post("/api/scan", json={"categories": "", "queries": ""}).status_code == 400


def test_scan_lifecycle(client, monkeypatch):
    c, server = client

    def fake_run(settings, *, dadata_token=None, progress=None, on_collect=None, on_phase=None, on_enrich=None):
        if progress:
            progress(1, 1)
        return [Lead(url="https://old.ru", domain="old.ru", outdated_score=88,
                     signals=["нет HTTPS", "нет meta viewport"],
                     contacts=Contacts(phones=["+7 843 000-00-00"], emails=["a@old.ru"]),
                     enrichment=Enrichment(official_name="ООО Тест", revenue=5_000_000))]

    monkeypatch.setattr(server.pipeline, "run", fake_run)

    start = c.post("/api/scan", json={"categories": "стоматология", "cities": "Казань"}).json()
    job_id = start["job_id"]
    assert "Яндекс" in " ".join(start["warnings"]) or start["warnings"] == []  # предупреждение о ключах

    job = {}
    for _ in range(50):
        job = c.get(f"/api/scan/{job_id}").json()
        if job["status"] in ("done", "error"):
            break
        time.sleep(0.05)
    assert job["status"] == "done", job
    assert job["count"] == 1
    assert job["leads"][0]["outdated_score"] == 88
    assert job["leads"][0]["revenue"] == 5_000_000
    assert job["leads"][0]["priority"] in ("A", "B", "C")
    assert job["summary"]["total"] == 1
    assert job["summary"]["corporate_email"] == 1  # a@old.ru на домене old.ru
    # письмо сгенерировано и приложено к строке
    assert "old.ru" in job["leads"][0]["pitch_body"]
    assert job["leads"][0]["pitch_subject"]
    assert job["leads"][0]["status"] == ""

    # экспорт
    csv = c.get(f"/api/scan/{job_id}/export.csv")
    assert csv.status_code == 200 and "old.ru" in csv.text
    assert c.get(f"/api/scan/{job_id}/export.json").status_code == 200


def test_scan_surfaces_phase_and_provider_warning(client, monkeypatch):
    """Фаза обогащения и ошибка провайдера доходят до статуса задачи (для UI)."""
    c, server = client
    import logging

    def fake_run(settings, *, dadata_token=None, progress=None, on_collect=None,
                 on_phase=None, on_enrich=None):
        if on_phase:
            on_phase("enrich")
        if on_enrich:
            on_enrich(3, 5)
        # эмулируем ошибку поисковика — она должна всплыть в warnings
        logging.getLogger("scanner.search").warning("Yandex Cloud searchAsync HTTP 403: denied")
        if progress:
            progress(1, 1)
        return [Lead(url="https://old.ru", domain="old.ru", outdated_score=50,
                     signals=["нет HTTPS"])]

    monkeypatch.setattr(server.pipeline, "run", fake_run)
    jid = c.post("/api/scan", json={"categories": "стоматология"}).json()["job_id"]
    job = {}
    for _ in range(50):
        job = c.get(f"/api/scan/{jid}").json()
        if job["status"] in ("done", "error"):
            break
        time.sleep(0.05)
    assert job["status"] == "done"
    assert job["enrich_total"] == 5                       # фаза обогащения отражена
    assert any("403" in w for w in job["warnings"])       # ошибка провайдера видна в UI


def test_lead_state_persistence(client):
    c, _ = client
    assert c.get("/api/leads/state").json() == {}
    r = c.post("/api/leads/state", json={"domain": "old.ru", "status": "написал"}).json()
    assert r["status"] == "написал"
    assert c.get("/api/leads/state").json()["old.ru"]["status"] == "написал"
    # заметку можно добавить, не сбрасывая статус
    c.post("/api/leads/state", json={"domain": "old.ru", "note": "звонил, перезвонят"})
    st = c.get("/api/leads/state").json()["old.ru"]
    assert st["status"] == "написал" and st["note"] == "звонил, перезвонят"

    # статус звонка и дата «перезвонить»
    c.post("/api/leads/state", json={"domain": "old.ru", "status": "перезвонить", "callback": "2026-08-01"})
    st = c.get("/api/leads/state").json()["old.ru"]
    assert st["status"] == "перезвонить" and st["callback"] == "2026-08-01"
    assert st["note"] == "звонил, перезвонят"  # заметка не потерялась

    # сумма сделки + регулярная поддержка + прототип при переводе в клиенты
    c.post("/api/leads/state", json={"domain": "old.ru", "status": "клиент",
                                     "deal_amount": 60000, "mrr": 5000,
                                     "prototype_url": "https://proto.lovable.app"})
    st = c.get("/api/leads/state").json()["old.ru"]
    assert st["status"] == "клиент" and st["deal_amount"] == 60000
    assert st["mrr"] == 5000 and st["prototype_url"] == "https://proto.lovable.app"
    assert st["callback"] == "2026-08-01"  # прочие поля на месте


def test_lead_state_rejects_bad_status(client):
    c, _ = client
    assert c.post("/api/leads/state", json={"domain": "x.ru", "status": "чепуха"}).status_code == 400


def test_base_accumulates_scanned_leads(client, monkeypatch):
    c, server = client
    assert c.get("/api/base").json()["count"] == 0

    def fake_run(settings, *, dadata_token=None, progress=None, on_collect=None, on_phase=None, on_enrich=None):
        if progress:
            progress(1, 1)
        return [Lead(url="https://old.ru", domain="old.ru", outdated_score=80, outreach_score=70,
                     signals=["нет HTTPS"], contacts=Contacts(emails=["a@old.ru"]))]

    monkeypatch.setattr(server.pipeline, "run", fake_run)

    def run_scan():
        jid = c.post("/api/scan", json={"categories": "стоматология", "cities": "Казань"}).json()["job_id"]
        for _ in range(50):
            if c.get(f"/api/scan/{jid}").json()["status"] in ("done", "error"):
                break
            time.sleep(0.05)

    run_scan()
    base = c.get("/api/base").json()
    assert base["count"] == 1
    assert base["leads"][0]["domain"] == "old.ru"
    assert base["leads"][0]["pitch_body"]  # письмо сохранено в базе

    # статус, выставленный отдельно, виден в базе; повторный скан не плодит дубль
    c.post("/api/leads/state", json={"domain": "old.ru", "status": "написал"})
    run_scan()
    base = c.get("/api/base").json()
    assert base["count"] == 1                       # дедуп по домену
    assert base["leads"][0]["status"] == "написал"  # статус подтянулся


def test_smtp_config_roundtrip(client):
    c, _ = client
    assert c.get("/api/config").json()["smtp"]["configured"] is False
    c.post("/api/secrets", json={"smtp_host": "smtp.yandex.ru", "smtp_port": "465",
                                 "smtp_user": "me@yandex.ru", "smtp_password": "app-pass"})
    smtp = c.get("/api/smtp").json()
    assert smtp["configured"] is True and smtp["smtp_user"] == "me@yandex.ru"
    assert "password" not in smtp  # пароль не отдаём наружу


def test_send_one_marks_written(client, monkeypatch):
    c, server = client
    sent = []
    monkeypatch.setattr(server.mailer, "is_configured", lambda: True)
    monkeypatch.setattr(server.mailer, "send_email", lambda to, s, b: sent.append((to, s, b)))

    r = c.post("/api/send", json={"domain": "firma.ru", "to": "info@firma.ru",
                                  "subject": "Тема", "body": "Текст"})
    assert r.status_code == 200 and sent == [("info@firma.ru", "Тема", "Текст")]
    assert c.get("/api/leads/state").json()["firma.ru"]["status"] == "написал"


def test_send_requires_smtp(client, monkeypatch):
    c, server = client
    monkeypatch.setattr(server.mailer, "is_configured", lambda: False)
    r = c.post("/api/send", json={"domain": "x.ru", "to": "a@x.ru", "subject": "s", "body": "b"})
    assert r.status_code == 400


def test_bulk_send_throttled(client, monkeypatch):
    c, server = client
    sent = []
    monkeypatch.setattr(server.mailer, "is_configured", lambda: True)
    monkeypatch.setattr(server.mailer, "send_email", lambda to, s, b: sent.append(to))
    monkeypatch.setattr(server.time, "sleep", lambda *_: None)  # без реальных пауз

    # заранее положим лид с почтой в базу
    server.STORE.upsert_leads([{"domain": "firma.ru", "emails": "info@firma.ru",
                                "outreach_score": 70, "pitch_subject": "Тема", "pitch_body": "Текст"}])
    start = c.post("/api/send/bulk", json={"domains": ["firma.ru"]}).json()
    sid = start["send_id"]
    for _ in range(50):
        st = c.get(f"/api/send/{sid}").json()
        if st["done"]:
            break
        time.sleep(0.02)
    assert st["done"] and st["sent"] == 1
    assert sent == ["info@firma.ru"]
    assert c.get("/api/leads/state").json()["firma.ru"]["status"] == "написал"


def test_screenshot_endpoint(client, monkeypatch):
    c, server = client

    def fake_capture(url, out, **k):
        from pathlib import Path
        p = Path(out); p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"\x89PNG\r\n\x1a\n"); return p

    monkeypatch.setattr(server.screenshot, "capture", fake_capture)
    r = c.get("/api/screenshot/example.ru")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/png")
    # второй запрос отдаёт из кэша (capture не нужен) — файл уже есть
    assert c.get("/api/screenshot/example.ru").status_code == 200


def test_screenshot_bad_domain(client):
    c, _ = client
    assert c.get("/api/screenshot/bad!name").status_code == 400


def test_revenue_check(client, monkeypatch):
    c, server = client
    from scanner.models import Enrichment
    monkeypatch.setenv("DADATA_TOKEN", "x")
    monkeypatch.setattr(server.enrich, "lookup_verbose",
                        lambda inn=None, name=None, **k: (Enrichment(
                            official_name="ООО Тест", revenue=12_000_000, status="ACTIVE"), None))
    r = c.post("/api/revenue", json={"domain": "firma.ru", "inn": "7707083893", "company": "Тест"})
    assert r.status_code == 200
    assert r.json()["revenue"] == 12_000_000 and r.json()["official_name"] == "ООО Тест"
    assert r.json()["found"] is True
    assert r.json()["error"] is None


def test_revenue_requires_token(client, monkeypatch):
    c, server = client
    monkeypatch.delenv("DADATA_TOKEN", raising=False)
    assert c.post("/api/revenue", json={"domain": "x.ru", "inn": "7707083893"}).status_code == 400


def test_revenue_surfaces_dadata_error(client, monkeypatch):
    """Плохой ключ/лимит DaData доходит до UI как понятный текст, а не пустой ответ."""
    c, server = client
    from scanner.models import Enrichment
    monkeypatch.setenv("DADATA_TOKEN", "x")
    monkeypatch.setattr(server.enrich, "lookup_verbose",
                        lambda inn=None, name=None, **k: (Enrichment(), "DaData отклонил ключ (403)"))
    d = c.post("/api/revenue", json={"domain": "x.ru", "inn": "7707083893"}).json()
    assert d["found"] is False
    assert "403" in d["error"]


def test_index_served(client):
    c, _ = client
    html = c.get("/").text
    assert "site-scanner" in html and "Запустить скан" in html


def test_scanner_logs_reach_stdout():
    """У логгера движка должен быть обработчик: без него INFO-разбор прогона
    уходил в logging.lastResort и не попадал в docker compose logs вообще."""
    import logging

    log = logging.getLogger("scanner")
    assert log.handlers, "у логгера scanner нет обработчика — логи прогона не видны"
    assert log.level <= logging.INFO


def test_screenshot_reports_missing_browser(tmp_path, monkeypatch):
    """Chromium в образе необязателен: скачивание с CDN Google доступно не
    отовсюду и раньше роняло сборку целиком. Если браузера нет — понятная
    ошибка, а не стектрейс Playwright."""
    from webapp import screenshot

    monkeypatch.setenv("CHROMIUM_PATH", str(tmp_path / "нет-такого-файла"))
    with pytest.raises(RuntimeError, match="Chromium не найден"):
        screenshot.capture("https://example.com", tmp_path / "shot.png")


# --------------------------------------------------------------------------- #
# Мусорные лиды: помеченный домен не должен возвращаться в новых сканах
# --------------------------------------------------------------------------- #
def test_trash_status_accepted(client):
    from webapp.leads_store import TRASH

    c, _ = client
    r = c.post("/api/leads/state", json={"domain": "centrkim.ru", "status": TRASH,
                                         "note": "переехали на новый сайт"})
    assert r.status_code == 200
    state = c.get("/api/leads/state").json()["centrkim.ru"]
    assert state["status"] == TRASH and "переехали" in state["note"]


def test_statuses_exposed_to_frontend(client):
    """Список статусов отдаём с сервера, чтобы он не расходился с JS."""
    c, _ = client
    statuses = c.get("/api/config").json()["statuses"]
    assert "мусор" in statuses and "отказ" in statuses


def test_trash_domains_go_into_scan_settings(client):
    """Помеченный мусором домен уходит в скан как исключение — иначе он
    всплывал бы в каждом следующем прогоне."""
    from webapp import server

    c, _ = client
    c.post("/api/leads/state", json={"domain": "gov.ru", "status": "мусор"})
    c.post("/api/leads/state", json={"domain": "живой.ru", "status": "интерес"})

    assert server.trash_domains() == ["gov.ru"]
    s = server._build_settings(server.ScanRequest(queries="x"), "job1")
    assert s.skip_domains == ["gov.ru"]


# --- выгрузка сайта клиента ------------------------------------------------ #
@pytest.mark.parametrize("bad", ["", "не домен", "localhost", "http://", "site"])
def test_dump_rejects_bad_domain(client, bad):
    """Домен уходит в сетевой обход — мусор из формы отсекаем до запуска."""
    c, _ = client
    assert c.post("/api/dump", json={"domain": bad}).status_code in (400, 422)


def test_dump_list_reads_from_disk(client, tmp_path):
    """Список архивов читается с тома, а не из памяти процесса: задачи
    перезапуск контейнера не переживают, а собранные архивы обязаны."""
    c, _ = client
    (tmp_path / "dumps").mkdir(parents=True, exist_ok=True)
    (tmp_path / "dumps" / "projekt-doma.ru-2026-08-07-2019.zip").write_bytes(b"PK\x05\x06" + b"\0" * 18)

    data = c.get("/api/dumps").json()
    assert data["count"] == 1
    assert data["dumps"][0]["domain"] == "projekt-doma.ru"   # дефисы в домене не режем


@pytest.mark.parametrize("name", [
    "../../etc/passwd", "..%2fsecrets.local.json", "leads.sqlite",
    "site.ru.zip", "site.ru-2026-08-07-2019.zip.bak",
])
def test_dump_download_rejects_stray_names(client, name):
    """Имя архива приходит из URL. Пускаем только то, что сами и сгенерировали,
    иначе «../» отдала бы наружу ключи с тома."""
    c, _ = client
    assert c.get(f"/api/dumps/{name}").status_code in (400, 404)
    assert c.delete(f"/api/dumps/{name}").status_code in (400, 404)


def test_dump_download_and_delete(client, tmp_path):
    c, _ = client
    (tmp_path / "dumps").mkdir(parents=True, exist_ok=True)
    path = tmp_path / "dumps" / "site.ru-2026-08-07-2019.zip"
    path.write_bytes(b"PK\x05\x06" + b"\0" * 18)

    assert c.get("/api/dumps/site.ru-2026-08-07-2019.zip").status_code == 200
    assert c.delete("/api/dumps/site.ru-2026-08-07-2019.zip").json() == {"ok": True}
    assert not path.exists()
    assert c.get("/api/dumps").json()["count"] == 0


def test_dump_one_at_a_time(client, monkeypatch):
    """Две выгрузки разом душат и наш сервер, и чужой — вторую не пускаем."""
    from webapp import server

    c, _ = client
    server.DUMP_JOBS["busy"] = server.DumpJob(id="busy", domain="a.ru", status="running")
    try:
        assert c.post("/api/dump", json={"domain": "b.ru"}).status_code == 409
    finally:
        server.DUMP_JOBS.clear()
