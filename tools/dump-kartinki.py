#!/usr/bin/env python3
"""Куда ведут картинки в уже сделанной выгрузке.

Выгрузка приехала с нулём файлов — до этого скрипта причину выясняли
запросами к живому сайту, а песочница в российские домены не ходит. Здесь
ответ достаётся из архива, который уже лежит на томе: разбираем разметку теми
же правилами, что и обход, и показываем, куда ведут адреса картинок.

Запуск на сервере сканера (репозиторий в образ не копируется, поэтому скрипт
подаётся на вход, а не лежит внутри):

    cd /root/site-scanner-main
    docker compose exec -T app python - /data/webapp_data/dumps/домен-ДАТА.zip \
        < tools/dump-kartinki.py

Можно и по распакованной выгрузке: python tools/dump-kartinki.py clients/домен/full
"""

from __future__ import annotations

import sys
import zipfile
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scanner import mirror  # noqa: E402


def _pages(src: Path):
    """(имя, html) по всем страницам выгрузки — из zip или из папки."""
    if src.is_dir():
        for path in sorted(src.rglob("*")):
            if path.suffix.lower() in (".html", ".htm"):
                yield path.name, path.read_text(encoding="utf-8", errors="replace")
        return
    with zipfile.ZipFile(src) as zf:
        for name in zf.namelist():
            if name.lower().endswith((".html", ".htm")):
                yield name, zf.read(name).decode("utf-8", errors="replace")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    src = Path(argv[1])
    if not src.exists():
        print(f"нет такого файла: {src}")
        return 2

    # Хост берём из имени архива: mebel-ryazane.ru-2026-08-27-1249.zip
    host = src.name.split(".ru-")[0] + ".ru" if ".ru-" in src.name else src.stem
    hosts, prichiny = Counter(), Counter()
    primery: dict[str, str] = {}
    stranic = refs = svoi = 0

    for name, html in _pages(src):
        stranic += 1
        soup = BeautifulSoup(html, "lxml")
        adresa = [(el.get("src") or "").strip() for el in soup.find_all("img")]
        adresa += mirror._image_refs(soup)
        for val in adresa:
            if not val or val.startswith(("data:", "javascript:", "#")):
                continue
            refs += 1
            # Страницы лежат в архиве плоско, поэтому относительные адреса
            # достраиваем от корня сайта — нам важен хост и расширение.
            url = urljoin(f"https://{host}/", val)
            netloc = urlparse(url).netloc.lower()
            ext = mirror._ext(urlparse(url).path)
            hosts[netloc] += 1
            if not mirror._same_site(url, host):
                prichiny[f"чужой хост {netloc}"] += 1
            elif ext not in mirror.ASSET_EXT:
                prichiny["адрес без расширения — картинку отдаёт скрипт"] += 1
            else:
                svoi += 1
            primery.setdefault(netloc, url)

    print(f"Выгрузка: {src.name}")
    print(f"Страниц разобрано: {stranic}, адресов картинок в разметке: {refs}")
    print(f"Из них своих и скачиваемых: {svoi}")
    if not refs:
        print("\nАдресов картинок нет вовсе — их подставляет скрипт,"
              " а обход JavaScript не выполняет.")
    print("\nХосты:")
    for netloc, n in hosts.most_common(15):
        print(f"  {n:6d}  {netloc or '(относительный адрес)'}  ← {primery[netloc]}")
    if prichiny:
        print("\nПочему не поехали:")
        for reason, n in prichiny.most_common(10):
            print(f"  {n:6d}  {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
