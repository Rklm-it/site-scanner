"""Хранилище API-ключей: JSON-файл + синхронизация в переменные окружения.

Ключи вводятся в UI один раз, сохраняются в secrets.local.json (в .gitignore)
и подставляются в os.environ, откуда их читают модули поиска и обогащения.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# поле в UI -> переменная окружения
FIELDS = {
    "yandex_xml_user": "YANDEX_XML_USER",
    "yandex_xml_key": "YANDEX_XML_KEY",
    "yandex_api_key": "YANDEX_API_KEY",
    "yandex_folder_id": "YANDEX_FOLDER_ID",
    "google_api_key": "GOOGLE_API_KEY",
    "google_cse_cx": "GOOGLE_CSE_CX",
    "serpapi_key": "SERPAPI_KEY",
    "dadata_token": "DADATA_TOKEN",
}

_PATH = Path(os.environ.get("SCANNER_SECRETS", "secrets.local.json"))


def load_into_env() -> None:
    """Загружает сохранённые ключи в окружение (вызывается при старте сервера)."""
    if not _PATH.exists():
        return
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return
    for field, env in FIELDS.items():
        val = data.get(field)
        if val:
            os.environ[env] = str(val)


def save(values: dict[str, str]) -> None:
    """Сохраняет только непустые ключи и обновляет окружение."""
    current: dict[str, str] = {}
    if _PATH.exists():
        try:
            current = json.loads(_PATH.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            current = {}
    for field in FIELDS:
        val = (values.get(field) or "").strip()
        if val:
            current[field] = val
            os.environ[FIELDS[field]] = val
    _PATH.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")


def status() -> dict[str, bool]:
    """Какие ключи заданы (без раскрытия значений) — для индикаторов в UI."""
    return {field: bool(os.environ.get(env)) for field, env in FIELDS.items()}
