#!/usr/bin/env python3
"""Видимый текст и цены из выгрузки — без разворачивания её на диск.

Зачем отдельно от `dump-kartinki.py`: разбор клиента начинается не с картинок,
а с текстов. Их надо перенести на новый сайт дословно — «клиент узнаёт свои
слова и понимает, что с ним разбирались». Читать для этого полтораста мегабайт
HTML руками нельзя, а распаковывать выгрузку целиком негде: том общий с базой
лидов, и свободного места там бывает полгигабайта.

Поэтому скрипт работает **прямо по zip-архиву**, разбирая файлы по одному и
ничего не выкладывая на диск. На выходе — markdown, который кладётся в
`clients/<домен>/ТЕКСТЫ.md`.

Из зависимостей только BeautifulSoup: скрипт должен запускаться внутри
контейнера, собранного из старого кода, — `scanner` не импортируется.

Запуск на сервере сканера (репозиторий в образ не копируется, скрипт подаётся
на вход):

    cd /root/site-scanner-main

    # тексты «живого ядра»: всё, что не каталог
    docker compose exec -T app python - /data/razbor/<тег>/<часть>.zip \
        < tools/teksty-iz-vygruzki.py > clients/<домен>/ТЕКСТЫ.md

    # только нужные страницы
    docker compose exec -T app python - выгрузка.zip 'contacts*' 'services*' \
        < tools/teksty-iz-vygruzki.py

    # цены из карточек товара
    docker compose exec -T app python - выгрузка.zip --tovary \
        < tools/teksty-iz-vygruzki.py > clients/<домен>/ЦЕНЫ.tsv

Работает и по распакованной папке: python tools/teksty-iz-vygruzki.py clients/домен/full

**Цену ищем в трёх местах и печатаем, что нашли.** Разметка у каждого движка
своя, вслепую угадать нельзя: сначала микроразметка (`itemprop="price"`),
потом узлы с классом, где есть слово price, и только потом — числа рядом со
словом «руб» в видимом тексте. Первый прогон посмотреть глазами: если цены
уехали не те, чинить здесь, а не в выводе.
"""

from __future__ import annotations

import fnmatch
import json
import re
import sys
import zipfile
from pathlib import Path

from bs4 import BeautifulSoup

# Служебное: в текст страницы не идёт.
MUSOR = ("script", "style", "noscript", "svg", "iframe", "template")
# Каталожные страницы в «живое ядро» не входят: их тысячи и они однотипные.
KATALOG = ("catalog/", "personal/", "auth/", "bitrix/")
CENA = re.compile(r"(\d[\d  ]{0,9}(?:[.,]\d{1,2})?)\s*(?:руб|₽|р\.)", re.I)


def stranicy(istochnik: Path):
    """Отдаёт пары (имя, разметка) — из архива или из папки, не разворачивая."""
    if istochnik.is_dir():
        for put in sorted(istochnik.rglob("*.htm*")):
            yield str(put.relative_to(istochnik)), put.read_bytes()
        return
    with zipfile.ZipFile(istochnik) as zf:
        for imya in sorted(zf.namelist()):
            if imya.lower().endswith((".html", ".htm")):
                yield imya, zf.read(imya)


def razobrat(sory: bytes) -> BeautifulSoup:
    # Кодировку не угадываем: у выгрузки страницы уже сохранены в utf-8, а
    # автоопределение на коротких страницах врёт (см. CLAUDE.md, «Дом 1»).
    return BeautifulSoup(sory.decode("utf-8", "replace"), "lxml")


def tekst(soup: BeautifulSoup) -> str:
    for t in soup(MUSOR):
        t.decompose()
    telo = soup.find("main") or soup.find(id="content") or soup.body or soup
    stroki = [s.strip() for s in telo.get_text("\n").splitlines()]
    out, predydushchaya = [], ""
    for s in stroki:
        if not s or s == predydushchaya:
            continue
        out.append(s)
        predydushchaya = s
    return "\n".join(out)


def cena(soup: BeautifulSoup) -> str:
    uzel = soup.find(attrs={"itemprop": "price"})
    if uzel is not None:
        return (uzel.get("content") or uzel.get_text(" ", strip=True)).strip()
    for skript in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            dannye = json.loads(skript.string or "{}")
        except Exception:                                          # noqa: BLE001
            continue
        naydeno = re.search(r'"price"\s*:\s*"?([\d.]+)', json.dumps(dannye))
        if naydeno:
            return naydeno.group(1)
    uzel = soup.find(class_=re.compile("price", re.I))
    if uzel is not None:
        naydeno = CENA.search(uzel.get_text(" ", strip=True))
        if naydeno:
            return naydeno.group(1)
    naydeno = CENA.search(tekst(soup))
    return naydeno.group(1) if naydeno else ""


def zagolovok(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    return h1.get_text(" ", strip=True) if h1 else (soup.title.get_text(strip=True) if soup.title else "")


def main() -> None:
    args = [a for a in sys.argv[1:] if a]
    if not args:
        sys.exit(__doc__)
    istochnik = Path(args[0])
    if not istochnik.exists():
        sys.exit(f"нет такого пути: {istochnik}")
    tovary = "--tovary" in args
    shablony = [a for a in args[1:] if not a.startswith("--")]

    if tovary:
        print("файл\tназвание\tцена")
    for imya, sory in stranicy(istochnik):
        if shablony:
            if not any(fnmatch.fnmatch(imya, sh) for sh in shablony):
                continue
        elif tovary:
            if not imya.startswith("catalog/"):
                continue
        elif imya.startswith(KATALOG):
            continue
        soup = razobrat(sory)
        if tovary:
            print(f"{imya}\t{zagolovok(soup)}\t{cena(soup)}")
        else:
            print(f"\n## {zagolovok(soup)}\n\n`{imya}`\n\n```\n{tekst(soup)}\n```")


if __name__ == "__main__":
    main()
