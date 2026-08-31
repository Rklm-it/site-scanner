#!/usr/bin/env python3
"""Забрать выгрузку из релиза GitHub обратно на сервер — по одной части.

Части лежат ассетами релиза и на томе их нет: ради этого всё и делалось. Но
для разбора они нужны обратно, и тут важно не вернуть ту же проблему с диском.
Поэтому скрипт качает и распаковывает по одной части, удаляя архив сразу после
распаковки: пик по диску — одна часть, а не вся выгрузка.

manifest.json лежит в релизе отдельным файлом и весит килобайты: с него и
начинают, чтобы понять, что вообще в выгрузке, до скачивания фотографий.

Запуск на сервере сканера, из /root/site-scanner-main:

    # что вообще есть в релизе
    docker compose exec -T app python - --spisok < tools/vzyat-vygruzku.py

    # только manifest.json (килобайты)
    docker compose exec -T app python - textileopt.ru-2026-08-31-1642 --manifest \
        < tools/vzyat-vygruzku.py

    # части целиком, в /data/razbor/<тег>
    docker compose exec -T app python - textileopt.ru-2026-08-31-1642 \
        < tools/vzyat-vygruzku.py
"""

from __future__ import annotations

import os
import sys
import zipfile
from pathlib import Path

import requests

# Скрипт подаётся на вход контейнеру (`python - < tools/...`), поэтому корень
# проекта в путь надо добавить руками. Вне контейнера модулей может не быть —
# тогда работаем по переменным окружения, ключи всё равно берутся оттуда.
sys.path.insert(0, "/app")
API = "https://api.github.com"
try:
    from webapp import secrets_store
    secrets_store.load_into_env()
except Exception:                          # noqa: BLE001
    pass

KUDA = Path(os.environ.get("RAZBOR_DIR", "/data/razbor"))


def zagolovki() -> dict:
    return {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
            "Accept": "application/vnd.github+json"}


def relizy_spisok() -> list[dict]:
    repo = os.environ["GITHUB_DUMPS_REPO"]
    otvet = requests.get(f"{API}/repos/{repo}/releases",
                         headers=zagolovki(), timeout=30)
    otvet.raise_for_status()
    return otvet.json()


def nayti(teg: str) -> dict:
    repo = os.environ["GITHUB_DUMPS_REPO"]
    otvet = requests.get(f"{API}/repos/{repo}/releases/tags/{teg}",
                         headers=zagolovki(), timeout=30)
    if otvet.status_code == 404:
        sys.exit(f"релиза с тегом {teg} нет — посмотри список: --spisok")
    otvet.raise_for_status()
    return otvet.json()


def skachat(asset: dict, kuda: Path) -> Path:
    """Качает ассет потоком: гигабайт в память класть незачем."""
    put = kuda / asset["name"]
    with requests.get(asset["url"], stream=True, timeout=900,
                      headers={**zagolovki(), "Accept": "application/octet-stream"}) as r:
        r.raise_for_status()
        with put.open("wb") as f:
            for kusok in r.iter_content(1024 * 256):
                f.write(kusok)
    return put


def main() -> None:
    args = [a for a in sys.argv[1:] if a]
    if not os.environ.get("GITHUB_TOKEN") or not os.environ.get("GITHUB_DUMPS_REPO"):
        sys.exit("нет GITHUB_TOKEN / GITHUB_DUMPS_REPO — заполни их на вкладке «Ключи»")

    if "--spisok" in args:
        for r in relizy_spisok():
            razmer = sum(a["size"] for a in r.get("assets", [])) / 1048576
            print(f"{r['tag_name']:<40} {len(r.get('assets', []))} частей, {razmer:.0f} МБ")
        return

    teg = next((a for a in args if not a.startswith("--")), "")
    if not teg:
        sys.exit("укажи тег релиза (или --spisok)")

    reliz = nayti(teg)
    kuda = KUDA / teg
    kuda.mkdir(parents=True, exist_ok=True)

    tolko_manifest = "--manifest" in args
    for asset in sorted(reliz.get("assets", []), key=lambda a: a["name"]):
        if tolko_manifest and asset["name"] != "manifest.json":
            continue
        print(f"качаю {asset['name']} ({asset['size'] / 1048576:.1f} МБ)…", flush=True)
        fajl = skachat(asset, kuda)
        if fajl.suffix == ".zip":
            with zipfile.ZipFile(fajl) as zf:
                zf.extractall(kuda)
            # Архив удаляем сразу: держать и его, и распакованное — это ровно та
            # беда с диском, от которой уходили.
            fajl.unlink()
            print("  распакована и удалена")
    print(f"готово: {kuda}")


if __name__ == "__main__":
    main()
