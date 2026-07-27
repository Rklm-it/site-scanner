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

    def fake_run(settings, *, dadata_token=None, progress=None):
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

    # экспорт
    csv = c.get(f"/api/scan/{job_id}/export.csv")
    assert csv.status_code == 200 and "old.ru" in csv.text
    assert c.get(f"/api/scan/{job_id}/export.json").status_code == 200


def test_index_served(client):
    c, _ = client
    html = c.get("/").text
    assert "site-scanner" in html and "Запустить скан" in html
