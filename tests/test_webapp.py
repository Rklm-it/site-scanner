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

    def fake_run(settings, *, dadata_token=None, progress=None, on_collect=None):
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

    def fake_run(settings, *, dadata_token=None, progress=None, on_collect=None):
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
    monkeypatch.setattr(server.enrich, "lookup",
                        lambda inn=None, name=None, **k: Enrichment(
                            official_name="ООО Тест", revenue=12_000_000, status="ACTIVE"))
    server.STORE.upsert_leads([{"domain": "firma.ru", "company": "Тест",
                                "source_query": "стоматология Казань", "inn": "7707083893",
                                "outreach_score": 50}])
    r = c.get("/api/revenue/firma.ru")
    assert r.status_code == 200
    assert r.json()["revenue"] == 12_000_000 and r.json()["official_name"] == "ООО Тест"


def test_revenue_requires_token(client, monkeypatch):
    c, server = client
    monkeypatch.delenv("DADATA_TOKEN", raising=False)
    server.STORE.upsert_leads([{"domain": "x.ru", "outreach_score": 1}])
    assert c.get("/api/revenue/x.ru").status_code == 400


def test_index_served(client):
    c, _ = client
    html = c.get("/").text
    assert "site-scanner" in html and "Запустить скан" in html
