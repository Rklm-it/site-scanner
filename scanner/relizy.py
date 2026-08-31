"""Отправка выгрузки в релизы GitHub — чтобы она не лежала на томе.

Зачем не в сам репозиторий: файлы больше 100 МБ GitHub отклоняет, история
пухнет навсегда, а во время коммита на диске нужны и файлы, и объекты git —
то есть вдвое больше места, чем сейчас. Ассеты релиза лежат отдельно от
истории, до 2 ГБ на файл, и репозиторий от них не растёт.

Токен берётся из окружения (`GITHUB_TOKEN`), репозиторий — из
`GITHUB_DUMPS_REPO` вида `Rklm-it/dumps`. Ключ в коде не хранится.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import requests

log = logging.getLogger("scanner.relizy")

API = "https://api.github.com"
TAJMAUT = 60
# Заливка гигабайтного файла по медленному каналу занимает минуты, и обрывать
# её по обычному таймауту нельзя: часть уже удалена с тома вместе с исходником.
TAJMAUT_ZALIVKI = 900


class NetuNastrojki(RuntimeError):
    """Не задан токен или репозиторий — отправлять некуда."""


def nastroeno() -> bool:
    return bool(os.environ.get("GITHUB_TOKEN") and os.environ.get("GITHUB_DUMPS_REPO"))


def _zagolovki() -> dict[str, str]:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise NetuNastrojki("нет GITHUB_TOKEN")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def sozdat_reliz(tag: str, zagolovok: str, opisanie: str = "") -> dict:
    """Создаёт релиз (или возвращает существующий с тем же тегом)."""
    repo = os.environ.get("GITHUB_DUMPS_REPO", "")
    if not repo:
        raise NetuNastrojki("нет GITHUB_DUMPS_REPO")

    otvet = requests.post(
        f"{API}/repos/{repo}/releases",
        headers=_zagolovki(), timeout=TAJMAUT,
        json={"tag_name": tag, "name": zagolovok, "body": opisanie, "draft": False,
              "prerelease": False},
    )
    if otvet.status_code == 422:
        # Тег уже есть — повторный запуск выгрузки того же сайта в ту же минуту.
        # Не ошибка: дозаливаем части в существующий релиз.
        est = requests.get(f"{API}/repos/{repo}/releases/tags/{tag}",
                           headers=_zagolovki(), timeout=TAJMAUT)
        est.raise_for_status()
        return est.json()
    otvet.raise_for_status()
    return otvet.json()


def zalit(reliz: dict, fajl: Path) -> str:
    """Заливает файл ассетом релиза, возвращает ссылку на скачивание."""
    # upload_url приходит шаблоном RFC 6570: '...assets{?name,label}'.
    adres = reliz["upload_url"].split("{", 1)[0]
    with fajl.open("rb") as f:
        otvet = requests.post(
            adres, headers={**_zagolovki(), "Content-Type": "application/zip"},
            params={"name": fajl.name}, data=f, timeout=TAJMAUT_ZALIVKI,
        )
    otvet.raise_for_status()
    return otvet.json()["browser_download_url"]


def proverit() -> tuple[bool, str]:
    """Быстрая проверка перед выгрузкой: доступен ли репозиторий на запись.

    Вызывается ДО обхода, а не после. Узнать про негодный токен, когда сайт уже
    скачан и части удалены с тома, значит потерять выгрузку целиком.
    """
    repo = os.environ.get("GITHUB_DUMPS_REPO", "")
    if not nastroeno():
        return False, "не заданы GITHUB_TOKEN и GITHUB_DUMPS_REPO"
    try:
        otvet = requests.get(f"{API}/repos/{repo}", headers=_zagolovki(), timeout=TAJMAUT)
    except requests.RequestException as exc:
        return False, f"GitHub недоступен: {exc}"
    if otvet.status_code == 404:
        return False, f"репозиторий {repo} не найден или токен без доступа к нему"
    if otvet.status_code in (401, 403):
        return False, "токен не подошёл (401/403): проверьте срок и права `contents: write`"
    if not otvet.ok:
        return False, f"GitHub ответил {otvet.status_code}"
    prava = otvet.json().get("permissions") or {}
    if not prava.get("push", True):
        return False, f"у токена нет права записи в {repo}"
    return True, repo
