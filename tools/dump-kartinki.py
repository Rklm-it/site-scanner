#!/usr/bin/env python3
"""Куда ведут картинки в уже сделанной выгрузке.

Выгрузка приехала с нулём файлов — до этого скрипта причину выясняли
запросами к живому сайту, а песочница в российские домены не ходит. Здесь
ответ достаётся из архива, который уже лежит на томе: разбираем разметку теми
же правилами, что и обход, и показываем, куда ведут адреса картинок.

Скрипт намеренно самостоятельный: из зависимостей только BeautifulSoup, а
`scanner` не импортируется вовсе. Иначе он не запустится там, где нужнее
всего — внутри контейнера, собранного из старого кода, до перевыгрузки.

Запуск на сервере сканера (репозиторий в образ не копируется, поэтому скрипт
подаётся на вход, а не лежит внутри):

    cd /root/site-scanner-main
    docker compose exec -T app python - /data/webapp_data/dumps/домен-ДАТА.zip \
        < tools/dump-kartinki.py

Можно и по распакованной выгрузке: python tools/dump-kartinki.py clients/домен/full

С ключом `--zamer` вдобавок измеряет вес картинок: качает несколько штук
вразнобой и считает, сколько места займёт вся выгрузка. Нужно потому, что
место на томе делится с базой лидов, а «3005 картинок» — это и 200 МБ, и
гигабайт, смотря что за файлы:

    docker compose exec -T app python - /data/webapp_data/dumps/домен-ДАТА.zip --zamer \
        < tools/dump-kartinki.py
"""

from __future__ import annotations

import random
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

# Те же правила, что и у обхода в scanner/mirror.py. Продублированы
# сознательно: диагностика должна работать в контейнере со старым кодом.
ASSET_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".bmp"}
IMG_ATTRS = ("data-src", "data-original", "data-lazy-src", "data-lazy",
             "data-echo", "data-image", "data-bg", "data-background")
SRCSET_ATTRS = ("srcset", "data-srcset")
CSS_URL = re.compile(r"""url\(\s*['"]?([^'")]+)['"]?\s*\)""", re.I)


def ext(path: str) -> str:
    tail = path.rsplit("/", 1)[-1]
    return ("." + tail.rsplit(".", 1)[1].lower()) if "." in tail else ""


def same_site(url: str, host: str) -> bool:
    netloc = urlparse(url).netloc.lower().split(":")[0]
    return netloc in (host, f"www.{host}")


def image_refs(soup) -> list[str]:
    """Все адреса картинок со страницы: src, ленивые атрибуты, srcset, фоны."""
    out: list[str] = []
    for el in soup.find_all(["img", "source"]):
        out.append((el.get("src") or "").strip())
        for attr in IMG_ATTRS:
            out.append((el.get(attr) or "").strip())
        for attr in SRCSET_ATTRS:
            # `srcset` — это «адрес 1x, адрес 2x»: берём адреса, дескрипторы нет
            for part in (el.get(attr) or "").split(","):
                out.append(part.strip().split(" ")[0].strip())
    for el in soup.find_all(attrs={"style": True}):
        out += [m.group(1).strip() for m in CSS_URL.finditer(el["style"])]
    for el in soup.find_all("style"):
        out += [m.group(1).strip() for m in CSS_URL.finditer(el.get_text())]
    return [v for v in out if v and not v.startswith(("data:", "javascript:", "#"))]


def pages(src: Path):
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


def zamerit(urls: list[str], skolko: int) -> None:
    """Сколько весит картинка на этом сайте — по выборке, а не по догадке.

    Без этого числа выгрузку не спланировать: 3005 картинок это и 180 МБ, и
    полтора гигабайта, а место на томе общее с базой лидов. Берём вразнобой,
    а не первые попавшиеся: в начале списка обычно логотипы и иконки шапки,
    по ним средний вес выходит втрое меньше настоящего.
    """
    try:
        import requests
    except ImportError:
        print("\nЗамер не сделан: в этом окружении нет requests.")
        return
    vyborka = random.Random(0).sample(urls, min(skolko, len(urls)))
    headers = {"User-Agent": "Mozilla/5.0 (compatible; site-scanner/1.0)"}
    vesa: list[int] = []
    oshibok = 0
    for url in vyborka:
        try:
            r = requests.get(url, headers=headers, timeout=15, stream=True)
            dlina = r.headers.get("Content-Length")
            ves = int(dlina) if dlina else len(r.content)
            r.close()
            if r.status_code < 400 and ves:
                vesa.append(ves)
            else:
                oshibok += 1
        except Exception:  # noqa: BLE001
            oshibok += 1
    if not vesa:
        print(f"\nЗамер не удался: ни один из {len(vyborka)} запросов не ответил."
              " Хост отдаёт картинки только браузеру — выгрузку планируем по"
              " верхней оценке.")
        return
    vesa.sort()
    sredniy = sum(vesa) / len(vesa)
    mediana = vesa[len(vesa) // 2]
    itogo_mb = sredniy * len(urls) / 1024 / 1024
    print(f"\nЗамер веса: скачано {len(vesa)} из {len(vyborka)}"
          f"{f', не ответили {oshibok}' if oshibok else ''}")
    print(f"  средний файл {sredniy / 1024:.0f} КБ, медиана {mediana / 1024:.0f} КБ, "
          f"самый тяжёлый {vesa[-1] / 1024:.0f} КБ")
    print(f"  вся выгрузка ≈ {itogo_mb:.0f} МБ на {len(urls)} картинок")
    # Пик — одна копия: файлы удаляются по мере упаковки в архив. Плюс запас,
    # который сканер держит под базу лидов и не отдаёт выгрузке.
    print(f"  на томе нужно ≈ {itogo_mb * 1.15 + 300:.0f} МБ свободных "
          f"(из них 300 сканер держит под базу лидов), "
          f"в поле «Объём, МБ» ставить {int(itogo_mb * 1.3) + 50}")


def main(argv: list[str]) -> int:
    zamer = 0
    argv = list(argv)
    if "--zamer" in argv:
        i = argv.index("--zamer")
        argv.pop(i)
        # После ключа может стоять число: сколько картинок качать.
        if i < len(argv) and argv[i].isdigit():
            zamer = int(argv.pop(i))
        else:
            zamer = 25
    if len(argv) != 2:
        # Лишние аргументы — почти всегда это `--zamer` на старой версии
        # скрипта: `git checkout` ветку не обновляет, если уже стоишь на ней,
        # и в контейнер уезжает файл из прошлого коммита. Молча показанная
        # справка выглядит как «скрипт сломался».
        lishnie = [a for a in argv[1:] if a.startswith("-")]
        if lishnie:
            print(f"Не понял аргументы: {' '.join(lishnie)}.\n"
                  f"Если это --zamer, а он не принялся — на сервере старая версия\n"
                  f"скрипта: сделайте `git pull` и повторите.\n")
        print(__doc__)
        return 2
    src = Path(argv[1])
    if not src.exists():
        print(f"нет такого файла: {src}")
        return 2

    # Хост берём из имени архива: mebel-ryazane.ru-2026-08-27-1249.zip
    m = re.match(r"([\w.-]+?\.[a-z]{2,})-\d{4}-\d{2}-\d{2}", src.name)
    host = m.group(1) if m else src.stem
    hosts, prichiny = Counter(), Counter()
    unikalnye: dict[str, set[str]] = {}
    primery: dict[str, str] = {}
    stranic = refs = svoi = 0

    for _, html in pages(src):
        stranic += 1
        soup = BeautifulSoup(html, "html.parser")
        for val in image_refs(soup):
            refs += 1
            # Страницы лежат в архиве плоско, поэтому относительные адреса
            # достраиваем от корня сайта — нам важен хост и расширение.
            # Якорь отрезаем: у lpgenerator один и тот же файл встречается как
            # `plan.jpg#size_594x376`, и без этого «уникальных» вышло бы вдесятеро
            # больше, чем файлов на самом деле.
            url = urljoin(f"https://{host}/", val).split("#")[0]
            netloc = urlparse(url).netloc.lower()
            hosts[netloc] += 1
            unikalnye.setdefault(netloc, set()).add(url)
            primery.setdefault(netloc, url)
            if not same_site(url, host):
                prichiny[f"чужой хост {netloc}"] += 1
            elif ext(urlparse(url).path) not in ASSET_EXT:
                prichiny["адрес без расширения — картинку отдаёт скрипт"] += 1
            else:
                svoi += 1

    print(f"Выгрузка: {src.name}  (хост считаем {host})")
    print(f"Страниц разобрано: {stranic}, адресов картинок в разметке: {refs}")
    print(f"Из них своих и скачиваемых обходом: {svoi}")
    if not refs:
        print("\nАдресов картинок нет вовсе — их подставляет скрипт,"
              " а обход JavaScript не выполняет.")
    if hosts:
        # Скачивать придётся уникальные, а не все упоминания: в шаблоне
        # конструктора одна и та же картинка стоит на каждой странице.
        print("\nХосты (упоминаний / уникальных адресов):")
        for netloc, n in hosts.most_common(15):
            kartinok = sum(1 for u in unikalnye[netloc]
                           if ext(urlparse(u).path) in ASSET_EXT)
            print(f"  {n:6d} / {len(unikalnye[netloc]):5d}  "
                  f"{netloc or '(относительный адрес)'}  "
                  f"— из них файлов-картинок {kartinok}\n"
                  f"          ← {primery[netloc]}")
        kartinki = sorted(u for us in unikalnye.values() for u in us
                          if ext(urlparse(u).path) in ASSET_EXT)
        print(f"\nВсего уникальных картинок к скачиванию: {len(kartinki)}")
        if zamer and kartinki:
            zamerit(kartinki, zamer)
    if prichiny:
        print("\nПочему не поехали:")
        for reason, n in prichiny.most_common(10):
            print(f"  {n:6d}  {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
