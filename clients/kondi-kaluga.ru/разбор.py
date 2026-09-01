#!/usr/bin/env python3
"""Разбор выгрузки kondi-kaluga.ru: каталог и список фотографий.

Скрипт, а не руками, по двум причинам. Первая — выгрузку пересняли бы, и всё
пришлось бы считать заново. Вторая важнее: на карточке товара внизу висит блок
«похожие товары» с такими же строками «Производитель / Мощность / Цена», и
если брать первое совпадение по каждому полю отдельно, цена приезжает от
чужого товара. Так у Carrier 42 NQV 5 кВт «цена» оказалась 5 068 000 рублей —
это цена соседнего Daikin из блока рекомендаций. Поэтому поля читаются одним
подряд идущим блоком, начиная со строки «Производитель:».

Запуск из папки клиента:  python3 разбор.py
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

FULL = Path(__file__).parent / "full"
POLE = re.compile(r"^(Производитель|Тип|Режим работы|Мощность|Цена):\s*(.+)$")
TOVAR = re.compile(r"^(kondicioner-|PLA-|MSMA1A|MFAMOV)")


def tekst(p: Path) -> list[str]:
    s = p.read_text(encoding="utf-8", errors="replace")
    s = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?s)<!--.*?-->", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr|h[1-6]|td)>", "\n", s)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    s = re.sub(r"[ \t\xa0]+", " ", s)
    return [l.strip() for l in s.split("\n") if l.strip()]


def put(url: str) -> str:
    return url.replace("https://www.kondi-kaluga.ru", "").strip("/")


def tovary() -> list[dict]:
    karta = json.loads((FULL / "manifest.json").read_text())
    faily = {p["file"]: p for p in karta["index"] if TOVAR.match(put(p["url"]))}
    out = []
    for f in sorted(faily):
        stroki = tekst(FULL / f)
        i = next((k for k, l in enumerate(stroki) if l.startswith("Производитель:")), None)
        pole: dict[str, str] = {}
        if i is not None:
            for l in stroki[i:i + 6]:          # только свой блок, не «похожие»
                m = POLE.match(l)
                if not m:
                    break
                pole[m.group(1)] = m.group(2).strip()
        c = re.match(r"([\d.,]+)", pole.get("Цена", "0"))
        # Название берём из h1 карточки, а не из текста страницы: первые
        # строки там — шапка с корзиной («Товаров: 0»), одинаковая везде.
        out.append({
            "url": "/" + put(faily[f]["url"]) + "/",
            "nazvanie": faily[f]["h1"] or faily[f]["title"] or f,
            "brend": pole.get("Производитель", "—"),
            "tip": pole.get("Тип", "—"),
            "moshch": pole.get("Мощность", "—"),
            "cena": int(float(c.group(1).replace(",", "."))) if c else 0,
        })
    return out


def katalog(ts: list[dict]) -> str:
    bez = [t for t in ts if not t["cena"]]
    ceny = sorted(t["cena"] for t in ts if t["cena"])
    brendy: dict[str, int] = {}
    for t in ts:
        brendy[t["brend"]] = brendy.get(t["brend"], 0) + 1
    sh = ["# Каталог kondi-kaluga.ru", "",
          f"Снято из выгрузки от 1 сентября 2026: **{len(ts)} карточек товара**.",
          f"Без цены — **{len(bez)}** ({len(bez) * 100 // len(ts)}%). "
          "У остальных цены от {} до {} ₽, медиана {} ₽.".format(
              *(f"{x:,}".replace(",", " ")
                for x in (ceny[0], ceny[-1], ceny[len(ceny) // 2]))), "",
          "«Производитель» на сайте смешан со страной: рядом стоят `MIDEA` и",
          "`Midea Китай`, `Великобритания` (это Mitsubishi) и `Италия Zanussi`.",
          "Так же он показан в фильтре подбора — то есть покупатель выбирает",
          "производителя из списка, где одна и та же марка встречается дважды.", "",
          "| Название | Марка на сайте | Тип | Мощность | Цена, ₽ | Адрес |",
          "|---|---|---|---|---|---|"]
    for t in sorted(ts, key=lambda x: (-x["cena"], x["nazvanie"])):
        sh.append(f"| {t['nazvanie']} | {t['brend']} | {t['tip']} | {t['moshch']} | "
                  f"{t['cena'] or '—'} | `{t['url']}` |")
    sh += ["", "## По маркам", "",
           "| Марка на сайте | Карточек |", "|---|---|"]
    for b, n in sorted(brendy.items(), key=lambda x: -x[1]):
        sh.append(f"| {b} | {n} |")
    return "\n".join(sh) + "\n"


def foto() -> str:
    svoi = sorted(p for p in (FULL / "uploads" / "gallery").iterdir()
                  if "_thumb" not in p.name)
    to = sorted(p for p in (FULL / "uploads" / "TO").rglob("*") if p.is_file())
    prod = list((FULL / "uploads" / "products").iterdir())
    sh = ["# Фотографии kondi-kaluga.ru", "",
          f"Своя съёмка: **в галерее {len(svoi)}**, **в разделах обслуживания и",
          f"установки {len(to)}**. Каталожных картинок производителей — {len(prod)},",
          "их в новый сайт не переносим: это чужие рендеры, а не работы компании.", "",
          "## Галерея «Фото наших работ»", ""]
    for p in svoi:
        sh.append(f"- `uploads/gallery/{p.name}` — {p.stat().st_size // 1024} КБ")
    sh += ["", "## Техобслуживание и установка", ""]
    for p in to:
        sh.append(f"- `{p.relative_to(FULL)}` — {p.stat().st_size // 1024} КБ")
    sh += ["", "## Чего не хватает", "",
           "Имена файлов галереи — это даты съёмки: `01112012005.jpg` — ноябрь",
           "2012, `06032013041.jpg` — март 2013. То есть **портфолио компании",
           "старше десяти лет**. Что на снимках: смотрели выборочно —",
           "внутренний блок крупным планом на стене пустой комнаты, наружный",
           "блок на облезлом фасаде. Кадры доказывают, что техника висит, и",
           "ничего больше: ни комнаты, ни людей, ни аккуратности монтажа.", "",
           "Для прототипа к звонку этого хватает. Для сдачи нужна съёмка, и",
           "просить её надо конкретно, а не «пришлите фотографии»:", "",
           "- 8–10 готовых установок в жилых комнатах, снятых так, чтобы было",
           "  видно помещение, а не только блок;",
           "- 3–4 наружных блока на фасаде — это то, чего боится заказчик",
           "  («мне испортят вид»);",
           "- аккуратная трасса в коробе и штроба до и после — доказательство",
           "  качества монтажа, которое словами не передать;",
           "- бригада за работой и техника: у них в прайсе есть автовышка и",
           "  альпинист, а на сайте ни одного такого кадра;",
           "- офис на Баррикад, 2а — на сайте нет ни одного снимка, куда",
           "  человек придёт.", "",
           "Снимать может любой монтажник на телефон, если сказать что именно.",
           "Это неделя без затрат, и она снимает главный риск прототипа: новый",
           "сайт строится вокруг фотографий, а их пока нет."]
    return "\n".join(sh) + "\n"


# Страницы, тексты которых переносятся на новый сайт. Каталог и пагинация сюда
# не идут: там нечего переносить, кроме карточек, а они в КАТАЛОГ.md.
DLYA_TEKSTOV = [
    ("index.html", "Главная"),
    ("about.html", "О компании"),
    ("montazh.html", "Установка (монтаж)"),
    ("tehnicheskoe-obsluzhivanie.html", "Техническое обслуживание"),
    ("remont.html", "Ремонт"),
    ("garantiya.html", "Гарантия"),
    ("pomosch-v-vybore.html", "Помощь в выборе"),
    ("climat.html", "Умный микроклимат (Тион)"),
    ("vakansii.html", "Вакансии"),
    ("okonnyy-kondicioner.html", "Оконный кондиционер"),
    ("mobilnyy-kondicioner.html", "Мобильный кондиционер"),
    ("nastennaya-split-sistema.html", "Настенная сплит-система"),
    ("kanalnaya-split-sistema.html", "Канальная сплит-система"),
    ("kassetnaya-split-sitema.html", "Кассетная сплит-система"),
    ("napolno-potolochnaya-split-sistema.html", "Напольно-потолочная"),
    ("kolonnaya-split-sistema.html", "Колонная сплит-система"),
    ("multi-split-sistema.html", "Мульти-сплит система"),
    ("multizonalnaya-sistema.html", "Мультизональная система"),
    ("invertor.html", "Инвертор"),
]


def shablon() -> set[str]:
    """Строки, которые есть больше чем на половине страниц, — это шапка, меню,
    фильтр и подвал. Без их отсева каждая страница на девять десятых состоит из
    списка производителей и цен фильтра."""
    schet: dict[str, int] = {}
    faily = sorted(FULL.glob("*.html"))
    for f in faily:
        for l in set(tekst(f)):
            schet[l] = schet.get(l, 0) + 1
    return {l for l, c in schet.items() if c > len(faily) / 2}


def teksty() -> str:
    obshchee = shablon()
    sh = ["# Тексты kondi-kaluga.ru дословно", "",
          "Для переноса на новый сайт. Снято скриптом из выгрузки, шапка, меню,",
          "фильтр и подвал вырезаны. Правки орфографии не делались сознательно —",
          "видно, что переписывать.", ""]
    for f, imya in DLYA_TEKSTOV:
        p = FULL / f
        if not p.exists():
            continue
        svoe = [l for l in tekst(p) if l not in obshchee]
        # Первые строки — заголовок вкладки, хлебные крошки и повтор h1: на
        # новом сайте всё это не нужно, а в файле мешает читать.
        svoe = [l for i, l in enumerate(svoe) if not (i < 4 and l.startswith("Главная"))]
        while len(svoe) > 1 and svoe[0] == svoe[1]:
            svoe.pop(0)
        adres = "/" if f == "index.html" else f"/{f[:-5]}/"
        sh += [f"## {imya} — `{adres}`", ""] + svoe + [""]
    return "\n".join(sh) + "\n"


if __name__ == "__main__":
    ts = tovary()
    Path("КАТАЛОГ.md").write_text(katalog(ts), encoding="utf-8")
    Path("ФОТО.md").write_text(foto(), encoding="utf-8")
    Path("ТЕКСТЫ.md").write_text(teksty(), encoding="utf-8")
    print(f"каталог: {len(ts)} товаров")
