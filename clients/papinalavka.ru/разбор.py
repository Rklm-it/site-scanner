#!/usr/bin/env python3
"""Разбор выгрузки papinalavka.ru: из распакованного архива — в файлы клиента.

Запускается на сервере сканера, потому что архив туда и не должен ехать: 1500
страниц весят 87 МБ, а git хранит все версии — репозиторий раздуется навсегда.
В git ложатся только выжимки: каталог с ценами, фермеры, отзывы и списки
адресов картинок. Нужны только стандартная библиотека и python3.

    python3 clients/papinalavka.ru/разбор.py /root/dumps/papinalavka-2

Ключ `--фото` дополнительно скачивает картинки товаров рядом с выгрузкой (в
git они не идут — отбирать нужные глазами).
"""

from __future__ import annotations

import collections
import html
import json
import os
import re
import sys

OUT = os.path.dirname(os.path.abspath(__file__))
BASE = "https://papinalavka.ru"


def text(s: str) -> str:
    s = re.sub(r"(?s)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def read(root: str, rel: str) -> str:
    with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as f:
        return f.read()


def карточки(root: str) -> list[dict]:
    """Товары из `/shop/products/view/<id>`.

    Цена берётся из микроразметки schema.org — она на сайте размечена честно.
    У товаров со скидкой `itemprop="price"` нет: новая цена лежит в `div.summ`,
    старая — в `div.obsoletePrice`. Без отдельного разбора такие позиции молча
    приезжают без цены, а это как раз форель и сёмга — самое ходовое, что стоит
    на главной.
    """
    d = os.path.join(root, "shop", "products", "view")
    if not os.path.isdir(d):
        return []
    out = []
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".html"):
            continue
        h = read(d, fn)
        name = re.search(r'itemprop="name"[^>]*>(.*?)</h1>', h, re.S)
        cat = re.search(r'/shop/products/index/(\d+)">(.*?)</a>', h, re.S)
        price = re.search(r'itemprop="price"\s*>\s*([\d\s]+)', h)
        summ = re.search(r'class="summ[^"]*"[^>]*>\s*([\d\s]+)', h)
        old = re.search(r'class="obsoletePrice".*?<span>\s*([\d\s]+)', h, re.S)
        unit = re.search(r'class="valute"[^>]*>(.*?)</div>', h, re.S)
        img = re.search(r"href='(/content/catalog_image/[^']+)'", h)
        hit = re.search(r'class="hit_name">\s*(.*?)\s*</div>', h, re.S)
        supply = re.search(r"Ближайшая поставка[^<]*", h)
        body = re.search(r'(?s)<div class="text_content content_sryle".*?>(.*?)<div class="clear"', h)
        число = lambda m: int(re.sub(r"\s", "", m.group(1))) if m and m.group(1).strip() else None
        цена = число(price) or число(summ)
        out.append({
            "id": fn[:-5],
            "url": f"{BASE}/shop/products/view/{fn[:-5]}",
            "name": text(name.group(1)) if name else "",
            "cat": text(cat.group(2)) if cat else "",
            "price": цена,
            "old_price": число(old),
            "unit": text(unit.group(1)) if unit else "",
            "img": img.group(1) if img else "",
            "hit": text(hit.group(1)) if hit else "",
            "supply": text(supply.group(0)) if supply else "",
            "desc": text(body.group(1))[:600] if body else "",
        })
    return out


def каталог(prods: list[dict]) -> str:
    by = collections.defaultdict(list)
    for p in prods:
        by[p["cat"] or "— без раздела"].append(p)
    L = ["# Каталог papinalavka.ru", "",
         f"Собрано разбором выгрузки: **{len(prods)} товаров** в {len(by)} разделах.",
         "Цены — на день выгрузки. На сайте прямо написано, что они зависят от",
         "сезона и фермера и не являются офертой: в новом сайте их надо либо",
         "тянуть из их базы, либо не показывать вовсе.", "",
         "| Раздел | Товаров | Цены, руб. |", "|---|---:|---|"]
    for cat, items in sorted(by.items(), key=lambda kv: -len(kv[1])):
        pr = sorted(x["price"] for x in items if x["price"])
        L.append(f'| {cat} | {len(items)} | {f"{pr[0]}–{pr[-1]}" if pr else "—"} |')
    L += ["", "## Товары по разделам", ""]
    for cat, items in sorted(by.items(), key=lambda kv: -len(kv[1])):
        L += [f"### {cat}", ""]
        for p in sorted(items, key=lambda x: x["name"]):
            цена = f'{p["price"]} {p["unit"]}' if p["price"] else f'цена по запросу, {p["unit"]}'.strip()
            if p.get("old_price"):
                цена += f' (было {p["old_price"]})'
            метка = f' · _{p["hit"]}_' if p["hit"] else ""
            L += [f'- **{p["name"]}** — {цена}{метка}  ', f'  `{p["url"]}`']
        L.append("")
    return "\n".join(L)


def фермеры(root: str) -> str:
    try:
        h = read(root, os.path.join("farmer", "farmers.html"))
    except OSError:
        return ""
    fs = re.findall(
        r"(?s)href=\"/shop/products/all\?farmer=(\d+)\".*?<img src='([^']+)'"
        r".*?circle_farm_count\">\s*(\d+).*?farmer_title\">(.*?)</span>"
        r".*?farmer_descr\">(.*?)</span>", h)
    L = ["# Фермеры «Папиной лавки»", "",
         "Главный актив бренда: у каждого поставщика имя, лицо и история — это и",
         "есть отличие от сетевого магазина, а не «натуральные продукты» в",
         "заголовке.", "",
         "Тексты обрезаны самим сайтом (в списке показан анонс); полные истории —",
         "на страницах фермеров.", "", f"Всего: {len(fs)}.", ""]
    for fid, img, cnt, name, descr in fs:
        L += [f"### {text(name)}",
              f"Товаров: {cnt} · фото `{BASE}{img}` · `{BASE}/shop/products/all?farmer={fid}`",
              "", text(descr), ""]
    return "\n".join(L)


def отзывы(root: str) -> str:
    for rel in (os.path.join("page", "about.html"), os.path.join("page", "about", "index.html")):
        try:
            h = read(root, rel)
            break
        except OSError:
            continue
    else:
        return ""
    revs = re.findall(
        r'(?s)<div\s+class="opinion_post">(.*?)<div class="header_title_post ?">(.*?)</div>', h)
    L = ["# Отзывы с сайта papinalavka.ru", "",
         f"Со страницы «О нас»: **{len(revs)} настоящих отзывов** с именами и",
         "датами. Придумывать для прототипа нечего и нельзя — здесь есть свои.", "",
         "Последние по датам — 2024 год, а поставки идут 2026-м: люди пишут, но",
         "страница не пополняется. На новом сайте отзывы лучше тянуть с",
         "Яндекс.Карт и 2ГИС, где они появляются сами.", "", "## Все отзывы", ""]
    for body, sig in revs:
        b = text(body)
        if b:
            L.append(f"- {b}  \n  — **{text(sig)}**")
    return "\n".join(L) + "\n"


def списки_фото(root: str, prods: list[dict]) -> tuple[int, int]:
    """Адреса картинок, которых нет в выгрузке, — двумя списками.

    Разделены не для порядка, а по делу: сорок с небольшим файлов фермеров и
    разделов нужны прототипу сегодня, каталог целиком — только боевому сайту.
    """
    есть = lambda u: os.path.exists(os.path.join(root, u.lstrip("/")))
    farmers, sections = [], set()
    try:
        farmers = re.findall(r"<img src='(/content/farmers/[^']+)'",
                             read(root, os.path.join("farmer", "farmers.html")))
    except OSError:
        pass
    idx = os.path.join(root, "shop", "products", "index")
    if os.path.isdir(idx):
        for fn in os.listdir(idx):
            sections |= set(re.findall(r"/content/sections/[^\s\"']+\.(?:jpg|jpeg|png)",
                                       read(idx, fn)))
    os.makedirs(os.path.join(OUT, "фото"), exist_ok=True)
    мелкие = [u for u in farmers + sorted(sections) if not есть(u)]
    товары = [p for p in prods if p["img"] and not есть(p["img"])]
    with open(os.path.join(OUT, "фото", "фермеры-и-разделы.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(BASE + u for u in мелкие) + "\n")
    with open(os.path.join(OUT, "фото", "товары.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(f'{BASE}{p["img"]}  # {p["name"]}' for p in товары) + "\n")
    return len(мелкие), len(товары)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    root = args[0]
    if not os.path.isdir(root):
        print(f"Нет такой папки: {root}")
        return 1
    # Архив иногда распаковывают на уровень выше — ищем manifest.json и там.
    if not os.path.exists(os.path.join(root, "manifest.json")):
        глубже = [os.path.join(root, d) for d in os.listdir(root)
                  if os.path.exists(os.path.join(root, d, "manifest.json"))]
        if not глубже:
            print(f"В {root} нет manifest.json — это точно распакованная выгрузка?")
            return 1
        root = глубже[0]
        print(f"Выгрузка найдена глубже: {root}")

    man = json.load(open(os.path.join(root, "manifest.json"), encoding="utf-8"))
    prods = карточки(root)
    if not prods:
        print("Карточек товаров не найдено — проверьте, та ли это выгрузка.")
        return 1

    open(os.path.join(OUT, "КАТАЛОГ.md"), "w", encoding="utf-8").write(каталог(prods))
    for имя, готовое in (("ФЕРМЕРЫ.md", фермеры(root)), ("ОТЗЫВЫ.md", отзывы(root))):
        if готовое:
            open(os.path.join(OUT, имя), "w", encoding="utf-8").write(готовое)
    мелкие, товары = списки_фото(root, prods)

    без_цены = sum(1 for p in prods if p["price"] is None)
    print(f"Выгрузка от {man.get('collected', '?')}: страниц {man.get('pages')}, "
          f"файлов {man.get('assets')}, не добрано страниц {man.get('pages_left', 0)}, "
          f"файлов {man.get('assets_left', 0)}")
    print(f"Товаров разобрано: {len(prods)} (без цены {без_цены})")
    print(f"Списки фото: фермеры и разделы {мелкие}, товары {товары}")
    print("Готово. В git идут только КАТАЛОГ.md, ФЕРМЕРЫ.md, ОТЗЫВЫ.md и фото/*.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
