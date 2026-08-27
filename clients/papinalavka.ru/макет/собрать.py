#!/usr/bin/env python3
"""Собирает макет главной страницы «Папиной лавки» одним HTML-файлом.

Данные — из выгрузки в `full/`: названия разделов, цены, фотографии товаров.
Картинки вшиваются в файл base64, чтобы макет открывался с флешки и уходил
клиенту одним вложением. Готовый файл в git не кладём — он собирается заново
за секунду, а весит два мегабайта.

    python3 clients/papinalavka.ru/макет/собрать.py [куда.html]
"""

from __future__ import annotations

import base64
import html as html_mod
import json
import os
import re
import sys
from urllib.parse import quote

ЗДЕСЬ = os.path.dirname(os.path.abspath(__file__))
ВЫГРУЗКА = os.path.join(os.path.dirname(ЗДЕСЬ), "full")


def текст(s: str) -> str:
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html_mod.unescape(s)).strip()


# Куда класть картинки. Пусто — вшиваем в HTML (файл уходит клиенту одним
# вложением). Заполнено ключом `--файлами` — кладём рядом отдельными файлами:
# на сервере так страница открывается заметно быстрее, картинки кэшируются
# браузером и не тащатся заново при каждом заходе.
РЯДОМ: dict[str, str | None] = {"папка": None}


def data_uri(путь: str) -> str:
    if РЯДОМ["папка"]:
        каталог = os.path.join(РЯДОМ["папка"], "img")
        os.makedirs(каталог, exist_ok=True)
        # Имя из пути внутри выгрузки: у сайта файлы зовутся `1.jpg` в разных
        # папках, и по одному имени они бы затёрли друг друга.
        имя = os.path.relpath(путь, ВЫГРУЗКА).replace(os.sep, "-").replace("content-", "")
        with open(путь, "rb") as f, open(os.path.join(каталог, имя), "wb") as g:
            g.write(f.read())
        return f"img/{имя}"
    with open(путь, "rb") as f:
        b = base64.b64encode(f.read()).decode()
    тип = "image/png" if путь.lower().endswith(".png") else "image/jpeg"
    return f"data:{тип};base64,{b}"


def шрифты() -> str:
    """Bitter и Golos Text — файлами внутрь макета, а не ссылкой на Google.

    Макет уходит клиенту вложением и открывается где угодно, в том числе там,
    где Google недоступен. Без шрифтов вид рассыпается на Georgia с Arial, и
    показывать такое нельзя. Нет сети при сборке — честно откатываемся на
    ссылку, о чём написано в выводе.
    """
    css_url = ("https://fonts.googleapis.com/css2?family=Bitter:wght@400;700"
               "&family=Golos+Text:wght@400;500;600&display=swap")
    ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
    try:
        import urllib.request

        def достать(url: str) -> bytes:
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read()

        css = достать(css_url).decode("utf-8")
        куски = []
        for подмножество, блок in re.findall(r"/\*\s*([\w-]+)\s*\*/\s*(@font-face\s*\{.*?\})",
                                            css, re.S):
            # Кириллица и латиница: остальные подмножества (греческий,
            # вьетнамский) в русском макете только весят.
            if подмножество not in ("cyrillic", "latin"):
                continue
            m = re.search(r"src: url\((https://[^)]+)\)", блок)
            if not m:
                continue
            b64 = base64.b64encode(достать(m.group(1))).decode()
            куски.append(блок.replace(m.group(1), f"data:font/woff2;base64,{b64}"))
        return "\n".join(куски)
    except Exception as exc:  # noqa: BLE001
        print(f"Шрифты не скачались ({type(exc).__name__}), останется ссылка на Google.")
        return ""


def логотип(имя: str) -> str | None:
    """Логотип клиента, если он лежит в `макет/лого/`.

    На сайте он подключён фоном из CSS и в выгрузку не попадает — файлы
    забираются отдельно (команда в `ФОТО.md`). Логотип узнают, шрифтовую
    надпись нет, поэтому он важнее любой типографики в шапке. Нет файла —
    честно возвращаем None и оставляем название текстом, а не рисуем
    самодельный знак: подделка хуже отсутствия.
    """
    путь = os.path.join(ЗДЕСЬ, "лого", имя)
    return data_uri(путь) if os.path.exists(путь) else None


def разделы() -> dict[str, str]:
    """id раздела → заглавная картинка (у каждого раздела она своя)."""
    корень = os.path.join(ВЫГРУЗКА, "content", "sections")
    out = {}
    for d in sorted(os.listdir(корень)):
        tmp = os.path.join(корень, d, "tmp")
        if os.path.isdir(tmp):
            files = sorted(os.listdir(tmp))
            if files:
                out[d] = os.path.join(tmp, files[0])
    return out


def имена_разделов() -> dict[str, str]:
    man = json.load(open(os.path.join(ВЫГРУЗКА, "manifest.json"), encoding="utf-8"))
    out = {}
    for p in man["index"]:
        m = re.match(r"^https://papinalavka\.ru/shop/products/index/(\d+)$", p["url"])
        if m:
            out[m.group(1)] = p.get("h1", "")
    return out


def товар(pid: str) -> dict | None:
    """Карточка товара с фотографией — из выгрузки, ничего не выдумывая."""
    файл = os.path.join(ВЫГРУЗКА, "shop", "products", "view", f"{pid}.html")
    папка = os.path.join(ВЫГРУЗКА, "content", "catalog_image", pid)
    if not (os.path.exists(файл) and os.path.isdir(папка)):
        return None
    h = open(файл, encoding="utf-8", errors="replace").read()
    имя = re.search(r'itemprop="name"[^>]*>(.*?)</h1>', h, re.S)
    цена = (re.search(r'itemprop="price"\s*>\s*([\d\s]+)', h)
            or re.search(r'class="summ[^"]*"[^>]*>\s*([\d\s]+)', h))
    было = re.search(r'class="obsoletePrice".{0,300}?<span>\s*([\d\s]+)', h, re.S)
    ед = re.search(r'class="valute"[^>]*>(.*?)</div>', h, re.S)
    метка = re.search(r'class="hit_name">\s*(.*?)\s*</div>', h, re.S)
    фото = sorted(os.listdir(папка))
    return {
        "имя": текст(имя.group(1)) if имя else "",
        "цена": re.sub(r"\s", "", цена.group(1)) if цена else "",
        "было": re.sub(r"\s", "", было.group(1)) if было else "",
        "ед": текст(ед.group(1)).replace("руб.", "").strip(),
        "метка": текст(метка.group(1)).lower() if метка else "",
        "фото": data_uri(os.path.join(папка, фото[0])),
    }


# Палитры. Тёплая взята из их собственного логотипа — гравюра напечатана
# сепией, и сайт вокруг неё собирается сам. Холодная («лёд и форель») была
# первой версией: она свежее для рыбы, но со знаком спорит. Держим обе, чтобы
# показать клиенту выбор, а не единственный вариант.
ПАЛИТРЫ = {
 "тёплая": """
  --вода:#3B2621; --лёд:#F1EFEA; --прилавок:#fff; --форель:#E4674A;
  --форель-тёмная:#CE5940; --зелень:#2F6B4F; --текст:#2C1E1A; --тихий:#7A6A60;
  --край:#E2DCD2; --на-тёмном:#F5EFE9; --подпись:#B39B8C; --строка:#D9CCC1;
  --линия-тёмная:#5A423A; --поле:#2E1D19; --поле-край:#5A423A; --подсказка:#A8907F;
  --вода-светлее:#4C332C; --текст-мягкий:#5C4A42; --успех:#8FD3A6;
 """,
 # Поле и лён: тёмный уходит в зелень, фон — небелёное полотно. Ближе к
 # «ферме», чем чистая сепия, и коралл на зелёном читается лучше всего.
 "луговая": """
  --вода:#2F3A2C; --лёд:#F2F1E9; --прилавок:#fff; --форель:#E4674A;
  --форель-тёмная:#CE5940; --зелень:#4A6B3A; --текст:#26301F; --тихий:#6F7A66;
  --край:#E1E2D6; --на-тёмном:#F1F3EA; --подпись:#A3AE97; --строка:#CCD3C2;
  --линия-тёмная:#4A5745; --поле:#242C21; --поле-край:#4A5745; --подсказка:#8E9A85;
  --вода-светлее:#3D4B38; --текст-мягкий:#4C5747; --успех:#8FD3A6;
 """,
 # Вода и зелень: холоднее луговой, но не ледяная. Рыба тут главная, а
 # молочное и ягоды не мёрзнут, как это было в первой холодной версии.
 "речная": """
  --вода:#23414A; --лёд:#EFF2F0; --прилавок:#fff; --форель:#E4674A;
  --форель-тёмная:#CE5940; --зелень:#3E7A55; --текст:#1B333A; --тихий:#647A80;
  --край:#DBE3E0; --на-тёмном:#EDF3F1; --подпись:#8FAAAF; --строка:#C6D6D6;
  --линия-тёмная:#3A5C64; --поле:#193038; --поле-край:#3A5C64; --подсказка:#7C989E;
  --вода-светлее:#2E525C; --текст-мягкий:#42606A; --успех:#8FD3A6;
 """,
 "холодная": """
  --вода:#0E2E38; --лёд:#EEF3F5; --прилавок:#fff; --форель:#E4674A;
  --форель-тёмная:#CE5940; --зелень:#2F6B4F; --текст:#14343E; --тихий:#5B7280;
  --край:#DCE5E9; --на-тёмном:#EAF2F5; --подпись:#7FA6B2; --строка:#B9D2DA;
  --линия-тёмная:#24505E; --поле:#0A242C; --поле-край:#2A5666; --подсказка:#6F97A4;
  --вода-светлее:#16414F; --текст-мягкий:#3A5A66; --успех:#8FD3A6;
 """,
}
ПАЛИТРА = ["речная"]

СТИЛЬ = """
:root{{{палитра}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--лёд);color:var(--текст);
  font:16px/1.55 "Golos Text","Helvetica Neue",Arial,sans-serif;-webkit-font-smoothing:antialiased}}
h1,h2,h3{{font-family:Bitter,Georgia,serif;font-weight:700;line-height:1.15;margin:0}}
a{{color:inherit}}
img{{max-width:100%;display:block}}
.обёртка{{max-width:1180px;margin:0 auto;padding:0 24px}}
/* Прилипшая доска перекрывает всё, к чему ведёт якорь: без этого «Что
   привозим» прокручивает так, что сам заголовок оказывается под ней. */
section[id],div[id]{{scroll-margin-top:96px}}
.пропустить{{position:absolute;left:-9999px}}
.пропустить:focus{{position:static;display:inline-block;margin:8px 24px;padding:8px 14px;
  background:var(--форель);color:#fff}}

/* шапка */
.шапка{{background:var(--прилавок);border-bottom:1px solid var(--край)}}
.шапка .обёртка{{display:flex;align-items:center;gap:24px;padding-top:18px;padding-bottom:18px}}
/* Лок-ап: их знак плюс имя шрифтом. В 58 пикселях плашка внутри знака
   нечитаема, а имя рядом читается всегда — знак при этом остаётся ихним. */
.лого{{text-decoration:none;color:inherit;display:grid;
  grid-template-columns:auto auto;align-items:center;column-gap:12px}}
.лого img{{height:78px;width:auto;grid-row:span 2;align-self:center}}
.лого b{{font-family:Bitter,Georgia,serif;font-size:26px;font-weight:700;
  letter-spacing:-.01em;align-self:end;line-height:1.1}}
section.тьма{{position:relative;overflow:hidden}}
.гравюра{{position:absolute;right:-40px;bottom:-30px;width:420px;height:310px;
  background-size:contain;background-repeat:no-repeat;background-position:right bottom;
  filter:invert(1);opacity:.09;pointer-events:none}}
@media (max-width:900px){{.гравюра{{display:none}}}}
.лого span{{font-family:"Golos Text",sans-serif;font-size:11px;font-weight:400;
  letter-spacing:.08em;text-transform:uppercase;color:var(--тихий);align-self:start;
  margin-top:3px}}
.шапка nav{{margin-left:auto;display:flex;align-items:center;gap:22px;font-size:15px}}
/* Город — не украшение: в каждом городе свои точки и свой телефон, и человек
   первым делом смотрит, работает ли лавка у него. */
.город{{display:flex;align-items:center;gap:8px;color:var(--тихий)}}
.город span{{font-size:12px;letter-spacing:.07em;text-transform:uppercase}}
.город select{{font:inherit;font-size:15px;padding:7px 10px;border:1px solid var(--край);
  border-radius:2px;background:var(--прилавок);color:var(--текст);cursor:pointer;max-width:170px}}

/* Шапка не должна переноситься в две строки: сначала уходит подпись под
   именем, потом слово «Город» — телефон и переключатель остаются всегда. */
@media (max-width:1150px){{
  .лого span{{display:none}}
  .шапка nav{{gap:16px}}
  .город span{{display:none}}
}}
.шапка nav a{{text-decoration:none;color:var(--тихий);white-space:nowrap}}
.шапка nav a:hover{{color:var(--текст)}}
.тел{{font-family:Bitter,Georgia,serif;font-size:19px;font-weight:700;white-space:nowrap;
  text-decoration:none!important;color:var(--текст)!important}}

/* доска поставок — фирменный элемент */
.доска{{position:sticky;top:0;z-index:20;background:var(--вода);color:var(--на-тёмном)}}
.доска .обёртка{{display:grid;grid-template-columns:auto 1fr auto;gap:32px;align-items:center;
  padding-top:16px;padding-bottom:16px}}
.доска.сжата .обёртка{{padding-top:8px;padding-bottom:8px}}
.дата{{font-family:Bitter,Georgia,serif;font-size:26px;font-weight:700;white-space:nowrap}}
.доска.сжата .дата{{font-size:19px}}
.дата small{{display:block;font-family:"Golos Text",sans-serif;font-size:11px;font-weight:400;
  letter-spacing:.09em;text-transform:uppercase;color:var(--подпись);margin-bottom:2px}}
.доска.сжата .дата small{{display:none}}
.везём{{font-size:14px;color:var(--строка);max-height:44px;overflow:hidden}}
.доска.сжата .везём{{max-height:22px}}
.срок{{text-align:right;font-size:14px;white-space:nowrap;border-left:1px solid var(--линия-тёмная);padding-left:24px}}
.срок b{{display:block;font-family:Bitter,Georgia,serif;font-size:18px}}

/* первый экран */
.экран{{padding:64px 0 56px}}
.экран .обёртка{{display:grid;grid-template-columns:1.15fr .85fr;gap:56px;align-items:center}}
.экран h1{{font-size:46px;letter-spacing:-.02em}}
.экран p{{font-size:18px;color:var(--текст-мягкий);max-width:34em;margin:20px 0 28px}}
.кнопки{{display:flex;align-items:center;gap:20px;flex-wrap:wrap}}
.кнопка{{display:inline-block;background:var(--форель);color:#fff;text-decoration:none;
  padding:14px 26px;border-radius:2px;font-weight:600;border:0;cursor:pointer;font-size:16px;
  font-family:inherit}}
.кнопка:hover{{background:var(--форель-тёмная)}}
.ссылка{{color:var(--вода);text-underline-offset:4px}}
.плитки{{display:grid;grid-template-columns:1fr 1fr;grid-auto-rows:1fr;gap:10px}}
.плитки img{{width:100%;height:100%;aspect-ratio:1;object-fit:cover;border-radius:2px}}

/* секции */
section{{padding:56px 0}}
section.бел{{background:var(--прилавок);border-top:1px solid var(--край);border-bottom:1px solid var(--край)}}
.заг{{display:flex;align-items:baseline;gap:16px;margin-bottom:28px;flex-wrap:wrap}}
.заг h2{{font-size:30px}}
.заг span{{color:var(--тихий);font-size:15px}}

/* разделы каталога — список-прайс, не крупные плитки: фото у клиента мелкие */
.разделы{{display:grid;grid-template-columns:repeat(3,1fr);gap:2px 28px}}
.раздел{{display:flex;align-items:center;gap:14px;padding:9px 10px;text-decoration:none;
  border-bottom:1px solid var(--край)}}
.раздел:hover{{background:var(--лёд)}}
.раздел img{{width:56px;height:56px;object-fit:cover;border-radius:2px;flex:0 0 56px}}
.раздел b{{font-weight:500;font-size:15px}}
.раздел i{{margin-left:auto;font-style:normal;color:var(--тихий);font-size:13px}}
.раздел.ядро{{background:var(--прилавок);border-left:3px solid var(--форель);padding-left:12px}}

/* товары */
.товары{{display:grid;grid-template-columns:repeat(4,1fr);gap:22px}}
.товар{{position:relative;background:var(--прилавок);border:1px solid var(--край);
  border-radius:2px;overflow:hidden;display:flex;flex-direction:column}}
/* overflow здесь обязателен: при увеличении картинка вылезала за рамку фото
   и наезжала на название с ценой. */
.товар .фото{{height:190px;background:var(--лёд);display:flex;align-items:center;
  justify-content:center;overflow:hidden}}
.товар .фото img{{max-height:190px;width:auto;object-fit:contain}}
.товар .низ{{padding:14px 16px 16px;display:flex;flex-direction:column;gap:8px;flex:1}}
.взаказ{{align-self:flex-start;background:none;border:1px solid var(--край);color:var(--вода);
  font:inherit;font-size:14px;padding:8px 16px;border-radius:2px;cursor:pointer;margin-top:2px}}
.взаказ:hover{{border-color:var(--форель);color:var(--форель)}}
.товар .имя{{font-size:15px;line-height:1.35;flex:1}}
.цена{{font-family:Bitter,Georgia,serif;font-size:21px;font-weight:700}}
.цена s{{font-family:"Golos Text",sans-serif;font-size:14px;font-weight:400;color:var(--тихий);
  margin-left:8px}}
.цена em{{font-style:normal;font-family:"Golos Text",sans-serif;font-size:13px;font-weight:400;
  color:var(--тихий)}}
.метка{{position:absolute;z-index:2;margin:10px;background:var(--зелень);color:#fff;
  font-size:11px;letter-spacing:.06em;text-transform:uppercase;padding:4px 9px;
  border-radius:2px}}
.метка.акция{{background:var(--форель)}}
.сноска{{color:var(--тихий);font-size:13px;margin-top:22px}}

/* как это работает */
.шаги{{display:grid;grid-template-columns:repeat(4,1fr);gap:0;margin-bottom:30px}}
.шаг{{padding:22px 26px 22px 0;position:relative}}
.шаг:not(:last-child)::after{{content:"";position:absolute;right:16px;top:30px;width:9px;height:9px;
  border-top:2px solid var(--форель);border-right:2px solid var(--форель);transform:rotate(45deg)}}
.шаг b{{display:block;font-family:Bitter,Georgia,serif;font-size:17px;margin-bottom:6px}}
.шаг span{{color:var(--тихий);font-size:14px}}
.правила{{border-top:1px solid var(--край);display:grid;grid-template-columns:repeat(3,1fr);gap:28px;padding-top:24px}}
.правила p{{margin:0;font-size:14.5px;color:var(--текст-мягкий)}}
.правила b{{font-family:Bitter,Georgia,serif}}

/* Цифры. Все настоящие и все проверяемые: год из ОГРНИП, лавки из контактов,
   товары и хозяйства из каталога, отзывы посчитаны на их же странице. Ни одной
   придуманной — такие спрашивают на первой же встрече. */
.цифры{{background:var(--вода);color:var(--на-тёмном)}}
.цифры .обёртка{{display:grid;grid-template-columns:repeat(5,1fr);gap:24px;
  padding-top:26px;padding-bottom:26px;text-align:center}}
.цифры b{{display:block;font-family:Bitter,Georgia,serif;font-size:34px;line-height:1.1}}
.цифры span{{font-size:13px;color:var(--строка)}}
@media (max-width:900px){{.цифры .обёртка{{grid-template-columns:repeat(2,1fr);text-align:left}}
  .цифры b{{font-size:26px}}}}

/* Оффер — крупной строкой, а не сноской: это причина заказать сегодня */
.оффер{{font-family:Bitter,Georgia,serif;font-size:21px;line-height:1.4;
  border-left:4px solid var(--форель);padding:6px 0 6px 18px;margin:26px 0 0}}

/* Выгода на карточке: цифру экономии видно раньше, чем цену */
.выгода{{position:absolute;z-index:2;right:0;top:0;background:var(--форель);color:#fff;
  font-family:Bitter,Georgia,serif;font-size:15px;padding:6px 10px;border-radius:0 0 0 2px}}

/* Кнопка, которая всегда под большим пальцем: на телефоне человек читает
   лёжа и не возвращается наверх ради заказа. */
.липкая{{display:none}}
@media (max-width:600px){{
  .липкая{{display:block;position:fixed;left:12px;right:12px;bottom:12px;z-index:30;
    text-align:center;box-shadow:0 6px 20px rgba(0,0,0,.25);
    opacity:0;pointer-events:none;transition:opacity .2s ease}}
  .липкая.видна{{opacity:1;pointer-events:auto}}
  body{{padding-bottom:76px}}
}}

/* Фермер крупным планом: широкая полоса, а не ещё одна карточка в сетке.
   Их отличие от сетевого магазина — люди, и на них должно быть место. */
.герой{{display:grid;grid-template-columns:auto 1fr;gap:28px;align-items:start;
  padding:30px 0;border-top:2px solid var(--вода);border-bottom:1px solid var(--край)}}
.герой .вензель{{width:88px;height:88px;font-size:28px}}
.герой h3{{font-size:24px;margin-bottom:4px}}
.герой .где{{color:var(--тихий);font-size:14px;margin-bottom:14px}}
.герой p{{margin:0;font-size:17px;max-width:44em}}
.герой .ещё{{margin-top:14px;font-size:14px;color:var(--тихий)}}
@media (max-width:600px){{.герой{{grid-template-columns:1fr;gap:16px}}}}

/* Заказчики. Не стена логотипов «для веса»: сначала строка словами, потом
   приглушённая полоса знаков. Логотипы серые и оживают под курсором — так
   они не спорят с товаром, ради которого человек пришёл. */
.заказчики{{display:flex;flex-wrap:wrap;gap:14px;align-items:center;margin-top:22px}}
/* Белая плашка уравнивает знаки: часть из них с прозрачным фоном, часть —
   JPEG с белым, и без подложки вторые выглядели бы белыми заплатками. */
.заказчики span{{display:flex;align-items:center;justify-content:center;
  width:118px;height:56px;background:var(--прилавок);border:1px solid var(--край);
  border-radius:2px}}
.заказчики img{{max-height:32px;max-width:92px;width:auto;opacity:.8;
  transition:opacity .2s ease}}
.заказчики span:hover img{{opacity:1}}
.заказчики+p{{color:var(--тихий);font-size:14px;margin-top:16px}}

/* советы: список, а не карточки — это тексты, а не товары */
.советы{{display:grid;grid-template-columns:1fr 1fr;gap:0 48px}}
.совет{{display:flex;gap:16px;align-items:baseline;padding:16px 0;
  border-bottom:1px solid var(--край);text-decoration:none;color:inherit}}
.совет:hover b{{color:var(--форель)}}
.совет b{{font-family:Bitter,Georgia,serif;font-size:17px;white-space:nowrap;
  transition:color .15s ease}}
.совет span{{color:var(--тихий);font-size:14px}}

/* фильтры витрины — их же деления на главной */
.фильтры{{display:flex;gap:8px;margin-left:auto;flex-wrap:wrap}}
.фильтры button{{font:inherit;font-size:14px;padding:7px 14px;border-radius:2px;
  border:1px solid var(--край);background:var(--прилавок);color:var(--текст);
  cursor:pointer;transition:border-color .15s ease,color .15s ease}}
.фильтры button:hover{{border-color:var(--форель)}}
.фильтры button[aria-pressed="true"]{{background:var(--вода);color:var(--на-тёмном);
  border-color:var(--вода)}}

/* переезд филиала — их новость, людям это важнее любого баннера */
.переезд{{border-left:3px solid var(--форель);padding:2px 0 2px 16px;margin-bottom:22px;
  font-size:15px}}
.переезд b{{font-family:Bitter,Georgia,serif}}

/* расписание поставок */
.график{{display:grid;grid-template-columns:repeat(3,1fr);gap:0;border-top:1px solid var(--край)}}
.день{{padding:20px 28px;border-right:1px solid var(--край)}}
.день:first-child{{padding-left:0}}
.день:last-child{{border-right:0;padding-right:0}}
.день b{{display:block;font-family:Bitter,Georgia,serif;font-size:20px}}
.день u{{display:block;text-decoration:none;color:var(--форель);font-size:12px;
  letter-spacing:.08em;text-transform:uppercase;margin-bottom:6px}}
.день span{{color:var(--тихий);font-size:14px}}

/* тёмная полоса: ломает чередование «белое — ледяное» и держит главное */
section.тьма{{background:var(--вода);color:var(--на-тёмном);border:0}}
section.тьма h2{{color:#fff}}
section.тьма .шаг span,section.тьма .правила p{{color:var(--строка)}}
section.тьма .правила{{border-top-color:var(--линия-тёмная)}}
section.тьма .шаг b,section.тьма .правила b{{color:#fff}}
section.тьма .график{{border-top-color:var(--линия-тёмная)}}
section.тьма .день{{border-right-color:var(--линия-тёмная)}}
section.тьма .день span{{color:var(--строка)}}

/* гарантия — одна строка во всю ширину, без карточки */
.гарантия{{font-family:Bitter,Georgia,serif;font-size:22px;line-height:1.4;max-width:30em}}
.гарантия+p{{color:var(--тихий);margin-top:14px;max-width:36em}}

/* подписка на поставки */
.подписка{{display:flex;gap:10px;flex-wrap:wrap;margin-top:20px;max-width:640px}}
.подписка input{{flex:1;min-width:280px;background:var(--прилавок);border:1px solid var(--край);
  color:var(--текст)}}
/* Оранжевый бережём для одного действия на экран — здесь кнопка тише */
.подписка .кнопка{{background:var(--вода)}}
.подписка .кнопка:hover{{background:var(--вода-светлее)}}
.подписка input::placeholder{{color:var(--тихий)}}

/* фермеры */
.фермеры{{display:grid;grid-template-columns:1fr 1fr;gap:8px 40px}}
.фермер{{display:flex;gap:18px;padding:16px 0;border-bottom:1px solid var(--край);align-items:flex-start}}
.вензель{{flex:0 0 60px;height:60px;border-radius:50%;background:var(--вода);color:var(--на-тёмном);
  display:flex;align-items:center;justify-content:center;font-family:Bitter,Georgia,serif;font-size:20px}}
.фермер b{{font-size:15.5px}}
.фермер span{{display:block;color:var(--тихий);font-size:13.5px;margin-top:3px}}
.фермер i{{margin-left:auto;font-style:normal;color:var(--тихий);font-size:13px;white-space:nowrap}}

/* отзывы */
.отзывы{{display:grid;grid-template-columns:1fr 1fr;gap:34px 48px}}
.отзыв p{{font-family:Bitter,Georgia,serif;font-size:18px;line-height:1.45;margin:0 0 12px}}
.отзыв cite{{font-style:normal;color:var(--тихий);font-size:14px}}
.отзыв::before{{content:"";display:block;width:34px;height:2px;background:var(--форель);margin-bottom:16px}}

/* лавки */
table{{width:100%;border-collapse:collapse;font-size:15px}}
th{{text-align:left;font-weight:500;color:var(--тихий);font-size:12px;letter-spacing:.07em;
  text-transform:uppercase;padding:0 14px 10px 0;border-bottom:1px solid var(--край)}}
td{{padding:14px 14px 14px 0;border-bottom:1px solid var(--край);vertical-align:top}}
td:first-child{{font-weight:500}}
td small{{display:block;color:var(--тихий);font-weight:400}}

/* заявка */
.заявка{{background:var(--вода);color:var(--на-тёмном)}}
.заявка .обёртка{{display:grid;grid-template-columns:1fr 1fr;gap:56px;align-items:start}}
.заявка h2{{font-size:30px;color:#fff}}
.заявка p{{color:var(--строка)}}
form{{display:grid;gap:12px}}
input,textarea{{font:inherit;padding:13px 15px;border:1px solid var(--поле-край);background:var(--поле);
  color:var(--на-тёмном);border-radius:2px;width:100%}}
input::placeholder,textarea::placeholder{{color:var(--подсказка)}}
textarea{{min-height:88px;resize:vertical}}
form small{{color:var(--подпись);font-size:12.5px}}
.готово{{color:var(--успех);font-size:14px;min-height:20px}}

footer{{background:var(--вода);color:var(--подпись);font-size:13.5px;padding:26px 0 40px}}
footer .обёртка{{display:flex;gap:24px;flex-wrap:wrap;justify-content:space-between}}
:focus-visible{{outline:2px solid var(--форель);outline-offset:2px}}
/* Движение. Три правила, по которым оно тут допущено: помогает понять
   (карточка отзывается на курсор), длится меньше четверти секунды, и его нет
   на телефоне, где половина заказов и где никакого наведения не существует.
   Плавающая рыба и «выезжание» секций сюда не попали намеренно: они отвлекают
   от товара и стареют быстрее, чем сайт окупится. */
.товар{{transition:box-shadow .2s ease,transform .2s ease}}
.товар:hover{{box-shadow:0 10px 28px rgba(0,0,0,.10);transform:translateY(-2px)}}
.товар .фото img{{transition:transform .3s ease}}
.товар:hover .фото img{{transform:scale(1.04)}}
.раздел img{{transition:transform .25s ease}}
.раздел:hover img{{transform:scale(1.06)}}
.кнопка,.взаказ{{transition:background .15s ease,border-color .15s ease,color .15s ease}}
.фермер .вензель{{transition:transform .25s ease}}
.фермер:hover .вензель{{transform:scale(1.06)}}

/* Гравюра в тёмной полосе чуть смещается при прокрутке — не эффект ради
   эффекта, а глубина: полоса перестаёт быть плоской заливкой. */
.гравюра{{transition:transform .6s cubic-bezier(.2,.7,.3,1)}}

@media (prefers-reduced-motion:reduce){{
  *{{transition:none!important;animation:none!important}}
  .товар:hover{{transform:none}}
  .товар:hover .фото img,.раздел:hover img{{transform:none}}
}}
@media (hover:none){{
  /* На телефоне наведения нет, а «залипший» ховер после тапа выглядит поломкой */
  .товар:hover{{transform:none;box-shadow:none}}
  .товар:hover .фото img,.раздел:hover img{{transform:none}}
}}

@media (max-width:900px){{
  .экран .обёртка,.заявка .обёртка{{grid-template-columns:1fr;gap:32px}}
  .экран h1{{font-size:32px}}
  .разделы,.товары,.шаги,.правила,.фермеры,.отзывы{{grid-template-columns:1fr 1fr}}
  .доска .обёртка{{grid-template-columns:1fr;gap:6px;text-align:left}}
  .везём{{display:none}}
  .срок{{text-align:left;border-left:0;padding-left:0;font-size:13px}}
  .срок b{{display:inline}}
  .шапка nav a:not(.тел){{display:none}}
  /* На 390 пикселях знак, город и телефон в одну строку не влезают: телефон
     обрезался, а логотип выдавливало за край. Две строки — знак с телефоном,
     под ними город во всю ширину. */
  .шапка .обёртка{{display:grid;grid-template-columns:auto 1fr;row-gap:10px;
    column-gap:12px;align-items:center;padding-top:12px;padding-bottom:12px}}
  .шапка nav{{display:contents}}
  /* Позиции задаём явно: в разметке город идёт раньше телефона, и без этого
     телефон уезжал на третью строку, а шапка занимала пол-экрана. */
  .тел{{font-size:17px;white-space:nowrap;justify-self:end;grid-row:1;grid-column:2}}
  .город{{grid-row:2;grid-column:1 / -1}}
  .город select{{width:100%;max-width:none}}
  .лого img{{height:60px}}
  .лого b{{font-size:20px}}
  .лого span{{display:none}}
  .город span{{display:none}}
  .шапка .обёртка{{gap:12px}}
  .срок b{{display:inline;margin-left:6px}}
}}
@media (max-width:600px){{
  /* Палец — не мышь: цели меньше 44 px промахиваются, а половина заказов
     идёт с телефона. Касается телефонов лавок, карт и кнопок в карточках. */
  td a,.шапка nav a,.ссылка,.взаказ{{display:inline-block;min-height:44px;
    line-height:28px;padding:8px 0}}
  /* Кнопки-деления витрины тоже пальцем: 44 пикселя — минимум, ниже промах */
  .фильтры button{{min-height:44px;padding:10px 16px}}
  .взаказ{{padding:10px 18px;line-height:1.2}}
  td small a{{padding-top:0}}
  .разделы,.товары,.шаги,.правила,.фермеры,.отзывы,.советы{{grid-template-columns:1fr}}
  /* Заголовок памятки не переносится (nowrap), и вместе с описанием строка
     вылезала за экран — на телефоне это горизонтальная прокрутка всей
     страницы. Ставим их друг под друга. */
  .совет{{flex-direction:column;gap:4px}}
  .совет b{{white-space:normal}}
  .день{{padding-right:16px}}
  .шаг:not(:last-child)::after{{display:none}}
  .шаг{{padding:14px 0;border-bottom:1px solid var(--край)}}
  section{{padding:38px 0}}
  .экран{{padding:36px 0}}
}}
"""


# Данные — из выгрузки и страницы контактов. Ничего придуманного: макет
# показывают живому владельцу компании, он узнаёт свои цифры и адреса.
КАТАЛОГ = [
    ("36", "Рыба", 57, True), ("79", "Икра", 12, True),
    ("67", "Пельмени, вареники, блинчики", 34, False),
    ("64", "Рыба солёная и копчёная", 28, False),
    ("82", "Колбасы, мясные деликатесы", 27, False),
    ("81", "Сыры", 27, False), ("85", "Йогурты натуральные", 27, False),
    ("56", "Эко кухня", 24, False), ("38", "Птица и яйца", 23, False),
    ("61", "Молочная ферма", 22, False), ("41", "Ягоды, грибы, овощи", 20, False),
    ("60", "Крафтовый шоколад, конфеты", 18, False), ("73", "Морепродукты", 18, False),
    ("70", "Сладости из детства", 16, False), ("51", "Масла первого отжима", 16, False),
    ("59", "Паштеты, специи, заготовки", 15, False), ("42", "Квас, чай и кофе", 15, False),
    ("35", "Крольчатина, баранина, говядина", 14, False), ("77", "Мармелад", 13, False),
    ("84", "Постное", 12, False), ("68", "Гриль-меню", 12, False),
    ("52", "Пастила из Белёва", 11, False), ("83", "Варенье", 11, False),
    ("71", "Урбечи", 10, False), ("63", "Хлеб", 10, False), ("43", "Мёд", 6, False),
    ("44", "Кедровые орешки и масло", 5, False), ("45", "Вода для жизни", 5, False),
    ("87", "Дичь", 4, False),
]
НЕДЕЛЯ = ["1263", "998", "996", "1393", "945", "1389", "68", "585"]
ФЕРМЕРЫ = [
    ("НФ", "Николай и Наталья Федоренко", "Карелия · форелеводческое хозяйство старше 20 лет", 3),
    ("ЕЧ", "Елена и Игорь Чередниченко", "Рамонский район · молочная ферма", 18),
    ("ЗК", "Зубаида и Казимир", "Карачаево-Черкесия · варенье и горный травяной чай", 24),
    ("НА", "Ферма Николая Алексеевича", "птица и кролик · деревенские яйца", 2),
    ("МА", "Матушка Анна", "Стефано-Махрищский монастырь, Владимирская область", 9),
    ("ДК", "Джон и Нина Кописки", "ферма «Богдарня»", 11),
    ("ЛА", "Лариса и Александр", "ягоды", 9),
    ("АФ", "Алексей Федотов", "дары Забайкалья", 14),
]
ОТЗЫВЫ = [
    ("Брал две форели (заказывали заранее) на Загоровского, 1. Обе рыбки достались "
     "с икрой. Сама рыбка красивая и наисвежайшая. Спасибо продавцам, очень "
     "приветливые и доброжелательные", "Дмитрий"),
    ("Потрясающая рыба, свежайшая икра, невероятные морепродукты. Абсолютно всё, "
     "что заказывали и заказываем, приносит положительные эмоции", "Алексей Морозов"),
    ("В рыбе весом около 3 кг оказалось 300 граммов икры. Рыба превосходная! "
     "Спасибо за помощь и такой подарок к Новому году", "Ирина"),
    ("Большое спасибо за рыбку! Забрал непотрошёную форель, и рыбка порадовала "
     "икрой. Приятный бонус", "Сергей"),
]
# Фермер крупным планом. Не «топ» и не рейтинг — рейтинг пришлось бы
# выдумать. Это редакционный формат: рассказываем по очереди о каждом, и
# начинаем с тех, кто везёт ядро ассортимента. Текст — их собственный анонс со
# страницы фермеров, полная история лежит на странице фермера.
ГЕРОЙ = {
    "имя": "Николай и Наталья Федоренко",
    "где": "Карелия · форелеводческое хозяйство",
    "позиций": 3,
    "текст": "Наша вкуснейшая и всеми любимая форель выращивается на семейном "
             "форелеводческом хозяйстве, существующем уже более двадцати лет и "
             "известном на всю страну. Чистейшие озёра находятся вдали от "
             "загрязнённых мест.",
    "вензель": "НФ",
}

# Их же материалы из раздела «Это интересно». Написаны в 2019-м, но не
# устаревают, а страх «я не умею разделывать рыбу» снимают лучше любой
# скидки — и приводят людей из поиска.
СОВЕТЫ = [
    ("Как разделать форель", "Пошагово: от целой рыбы до стейков и филе"),
    ("Дефрост — что это?", "Почему «охлаждённая из дефростированного сырья» — "
     "это размороженная рыба"),
    ("А лосось есть?", "Рыбы «лосось» не существует: разбираемся в семействе "
     "лососёвых"),
    ("Солим форель", "Три способа слабосолёной форели — выбирайте по вкусу"),
    ("Запекаем рыбу", "Шпаргалка для хозяйки: время, температура, специи"),
    ("Рыба детям", "С какого возраста, какая и сколько"),
]

# Корпоративные клиенты с их страницы «Наши клиенты и партнёры». Хозяин
# разрешил показывать. Это не «логотипы для веса»: перечислены настоящие
# компании со ссылками на их сайты, и для продуктовой доставки такой список
# значит больше любых слов о качестве.
# Знаком показываем только те, что читаются в полосе. У остальных внутри
# квадрата 200×200 мелкий текст: на высоте 34 пикселя он превращается в
# грязь и делает хуже всей полосе. Они остаются в списке словами — список от
# этого не врёт, а выглядит опрятно.
ЗАКАЗЧИКИ = [
    ("Сбербанк", "20_sber_logo_rus_h_wht_col_rgb01.png"),
    ("РЖД", "14_rzd_logo.png"),
    ("МегаФон", "16_megafonlogo.svg.png"),
    ("Росэнергоатом", "24_xr7k6xmaoyy.jpg"),
    ("Здравгород", "25_ekb4h0wj67iu106qc5xkw5pkqk3ke.png"),
]
ЗАКАЗЧИКИ_СЛОВАМИ = ["КидБург", "«Остров детства»", "«Твоё развитие»",
                     "«Интегра-РПК»", "ТМП-Пресс"]

ЛАВКИ = [
    ("ул. Карла Маркса, 94", "вход у арт-объекта «Царь-Рыба»", "9:00–20:00", "+7 950 758-55-05"),
    ("ул. Загоровского, 1", "ТЦ «Пять столиц», вход со стороны Шишкова", "9:00–22:00", "+7 929 009-40-11"),
    ("ул. Владимира Невского, 47", "за остановкой «Соборный»", "9:00–20:00", "+7 929 009-50-53"),
    ("ул. Ворошилова, 16", "за остановкой «Бахметьева», 1 этаж, парковка", "9:00–20:00", "+7 929 009-50-52"),
    ("ул. Старых Большевиков, 2", "левый берег", "9:00–20:00", "+7 929 009-50-23"),
    ("Новая Усмань, Дорожная, 30", "ТК «Южный парк»", "9:00–20:00", "+7 929 009-50-57"),
]
ПОСТАВКА = ("Охлаждённая форель из Осетии и Карелии, молоко, творог, сметана, сыры, "
            "домашняя птица, крольчатина, колбасы, мёд, малина и голубика")
# Расписание с их же страницы «Ближайшие поставки». Три даты вперёд — это и есть
# доказательство, что сайт живой: у конкурентов на этом месте «широкий ассортимент».
РАСПИСАНИЕ = [
    ("27 августа", "четверг", "Охлаждённая форель из Осетии и Карелии, мясо-молочная "
     "поставка, ягода"),
    ("1 сентября", "понедельник", "Молочная поставка с Большой Трещёвской фермы и малина"),
    ("3 сентября", "среда", "Охлаждённая морская форель и сёмга из Мурманска"),
]
# Города — из переключателя в шапке их сайта. Проверить у хозяина, где свои
# точки, а где партнёрские: на сайте это одним списком.
# Второй формой города — предложный падеж: «Лавки в Липецк» читается как
# машинный перевод, а страницу показывают живому человеку.
ГОРОДА = [("Воронеж", "Воронеже"), ("Нововоронеж", "Нововоронеже"),
          ("Россошь", "Россоши"), ("Липецк", "Липецке"), ("Анна", "Анне"),
          ("Борисоглебск", "Борисоглебске"), ("Лиски", "Лисках"),
          ("Бобров и Бутурлиновка", "Боброве и Бутурлиновке"),
          ("Москва", "Москве"), ("Минск", "Минске")]


def разметка_поиска() -> str:
    """JSON-LD про сеть лавок: адреса, часы, телефоны.

    У старого сайта размечены только карточки товаров, а сеть из шести точек в
    выдаче не видна вовсе. Для местного бизнеса это дороже любых ключевых слов:
    по запросу «фермерские продукты рядом» показывают то, что размечено.
    """
    точки = []
    for адрес, ориентир, часы, тел in ЛАВКИ:
        нач, кон = часы.split("–")
        точки.append({
            "@type": "Store",
            "name": f"Папина лавка — {адрес}",
            "address": {"@type": "PostalAddress", "addressLocality": "Воронеж",
                        "streetAddress": адрес, "addressCountry": "RU"},
            "telephone": тел,
            "openingHoursSpecification": {
                "@type": "OpeningHoursSpecification",
                "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday",
                              "Friday", "Saturday", "Sunday"],
                "opens": нач, "closes": кон},
        })
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "Папина лавка",
        "description": "Натуральные продукты с экоферм под заказ: поставка каждый четверг, "
                       "шесть лавок в Воронеже и доставка.",
        "telephone": "+7 929 009-50-55",
        "email": "papinalavka@gmail.com",
        "areaServed": "Воронеж и Воронежская область",
        "department": точки,
    }, ensure_ascii=False, indent=1)


def собрать() -> str:
    стиль = СТИЛЬ.format(палитра=ПАЛИТРЫ[ПАЛИТРА[0]])
    знак, знак_тёмный = логотип("logo1.png"), логотип("logo2.png")
    шапка_лого = (
        f'<a class="лого" href="/"><img src="{знак}" alt=""><b>Папина лавка</b>'
        f'<span>натуральные продукты экоферм</span></a>'
        if знак else
        '<div class="лого">Папина лавка'
        '<span>натуральные продукты экоферм · Воронеж</span></div>')
    # Гравюра из второго файла — в тёмную полосу фоном. Она штриховая, в
    # инверсии даёт светлые линии и работает как фирменная текстура, а не как
    # ещё одна картинка. Их собственный мотив: у конкурентов такого нет.
    гравюра = (f'<div class="гравюра" style="background-image:url({знак_тёмный})"></div>'
               if знак_тёмный else "")
    подвал_лого = ""
    разметка = разметка_поиска()
    значок = data_uri(os.path.join(ВЫГРУЗКА, "favicon.png"))
    вшитые = шрифты()
    ссылка = "" if вшитые else (
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Bitter:wght@400;700'
        '&family=Golos+Text:wght@400;500;600&display=swap" rel="stylesheet">')
    карт = разделы()
    ряды = []
    for cid, имя, сколько, ядро in КАТАЛОГ:
        фото = f'<img src="{data_uri(карт[cid])}" alt="{имя}">' if cid in карт else ""
        ряды.append(f'<a class="раздел{" ядро" if ядро else ""}" href="#">{фото}'
                    f'<b>{имя}</b><i>{сколько}</i></a>')

    карточки = []
    for pid in НЕДЕЛЯ:
        т = товар(pid)
        if not т:
            continue
        акция = " акция" if т["было"] else ""
        метка = (f'<span class="метка{акция}">{т["метка"]}</span>' if т["метка"] else "")
        было = f'<s>{т["было"]} ₽</s>' if т["было"] else ""
        выгода = ""
        if т["было"] and т["цена"]:
            разница = int(т["было"]) - int(т["цена"])
            if разница > 0:
                выгода = f'<div class="выгода">−{разница} ₽</div>'
        карточки.append(
            f'<article class="товар" data-метка="{т["метка"]}">{метка}{выгода}<div class="фото">'
            f'<img src="{т["фото"]}" alt="{т["имя"]}"></div><div class="низ">'
            f'<div class="имя">{т["имя"]}</div>'
            f'<div class="цена">{т["цена"]} ₽{было} <em>{т["ед"]}</em></div>'
            f'<button class="взаказ" type="button">В заказ</button></div></article>')

    ферм = "".join(
        f'<div class="фермер"><div class="вензель">{в}</div><div><b>{имя}</b>'
        f'<span>{про}</span></div><i>{n} поз.</i></div>'
        for в, имя, про, n in ФЕРМЕРЫ if имя != ГЕРОЙ["имя"])
    отз = "".join(f'<blockquote class="отзыв"><p>«{т}»</p><cite>{кто}</cite></blockquote>'
                  for т, кто in ОТЗЫВЫ)
    def карта(адрес: str) -> str:
        точка = quote(f"Воронеж {адрес}" if not адрес.startswith("Новая") else адрес)
        return f'<a href="https://yandex.ru/maps/?text={точка}" target="_blank" rel="noopener">на карте</a>'

    лавки = "".join(f'<tr><td>{а}<small>{о}</small></td><td>{ч}</td>'
                    f'<td><a href="tel:{т.replace(" ", "")}">{т}</a><small>{карта(а)}</small></td></tr>'
                    for а, о, ч, т in ЛАВКИ)
    всего_городов = len(ГОРОДА)
    города = "".join(f'<option data-где="{где}"{" selected" if г == "Воронеж" else ""}>'
                     f'{г}</option>' for г, где in ГОРОДА)
    # Логотипов может не быть на диске — тогда честно показываем названия
    # словами. Пустая строка вместо знака выглядит поломкой, подпись — нет.
    знаки = os.path.join(ЗДЕСЬ, "заказчики")
    заказчики = "".join(
        f'<span title="{имя}"><img src="{data_uri(os.path.join(знаки, файл))}" '
        f'alt="{имя}"></span>'
        if os.path.exists(os.path.join(знаки, файл)) else f"<span>{имя}</span>"
        for имя, файл in ЗАКАЗЧИКИ)
    словами = ", ".join(ЗАКАЗЧИКИ_СЛОВАМИ)
    советы = "".join(f'<a class="совет" href="#"><b>{з}</b><span>{о}</span></a>'
                     for з, о in СОВЕТЫ)
    график = "".join(f'<div class="день"><u>{д}</u><b>{дата}</b><span>{что}</span></div>'
                     for дата, д, что in РАСПИСАНИЕ)
    шаги = "".join(f'<div class="шаг"><b>{б}</b><span>{с}</span></div>' for б, с in [
        ("Выбираете продукты", "на сайте или по телефону"),
        ("Передаём заказ фермеру", "он собирает его лично для вас"),
        ("В четверг привозят свежее", "рыбу ловят, колбасы коптят под заказ"),
        ("Забираете или везём", "шесть лавок в городе или курьер"),
    ])

    return f"""<!doctype html>
<html lang="ru"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Папина лавка — натуральные продукты экоферм с доставкой в Воронеже</title>
<meta name="description" content="Фермерские продукты под заказ: свежая поставка каждый четверг,
шесть лавок в Воронеже и доставка. Форель из Карелии, молоко с фермы, сыры, мясо, ягоды.">
<link rel="icon" href="{значок}">
<!-- Ссылку на макет отправляют в мессенджере, и без этих трёх строк там
     показывается голый адрес. Картинку превью подставим, когда клиент даст
     нормальное фото: рисовать её из мелких снимков с их сайта нельзя. -->
<meta property="og:type" content="website">
<meta property="og:title" content="Папина лавка — натуральные продукты экоферм, Воронеж">
<meta property="og:description" content="Свежая поставка от фермеров каждый четверг.
Шесть лавок в Воронеже и доставка. Заказ принимаем до среды.">
<meta property="og:locale" content="ru_RU">
{ссылка}
<style>{вшитые}{стиль}</style>
<script type="application/ld+json">{разметка}</script>
</head><body>
<a class="пропустить" href="#каталог">Перейти к каталогу</a>

<header class="шапка"><div class="обёртка">
  {шапка_лого}
  <nav>
    <label class="город"><span>Город</span>
      <select id="город">{города}</select></label>
    <a href="#каталог">Что привозим</a><a href="#фермеры">Фермеры</a>
    <a href="#лавки">Где забрать</a>
    <a class="тел" href="tel:+79290095055">+7 929 009-50-55</a>
  </nav>
</div></header>

<div class="доска" id="доска"><div class="обёртка">
  <div class="дата"><small>Ближайшая поставка</small>четверг, 27 августа</div>
  <div class="везём">{ПОСТАВКА}</div>
  <div class="срок">До закрытия заказа<b id="осталось">считаем…</b></div>
</div></div>

<div class="экран"><div class="обёртка">
  <div>
    <h1>Всё, что вы закажете, привезут с фермы на этой неделе</h1>
    <p>Мы не держим склад. Рыба, которую вы заказываете, ещё плавает, а колбасы
       и сосиски ещё бегают по ферме вместе с курочками. Только так продукты
       бывают по-настоящему свежими.</p>
    <div class="кнопки">
      <a class="кнопка" href="#заявка">Заказать к четвергу</a>
      <a class="ссылка" href="#как">Как это работает</a>
    </div>
  </div>
  <div class="плитки">{"".join(f'<img src="{товар(p)["фото"]}" alt="{товар(p)["имя"]}">'
                               for p in НЕДЕЛЯ[:4] if товар(p))}</div>
</div></div>

<div class="цифры"><div class="обёртка">
  <div><b>с 2010</b><span>года возим фермерское</span></div>
  <div id="плитка-лавок"><b>6</b><span>лавок в Воронеже</span></div>
  <div><b>538</b><span>продуктов в каталоге</span></div>
  <div><b>12</b><span>проверенных хозяйств</span></div>
  <div><b>231</b><span>отзыв покупателей</span></div>
</div></div>

<section class="бел" id="каталог"><div class="обёртка">
  <div class="заг"><h2>538 продуктов от проверенных фермеров</h2>
    <span>29 разделов · цены зависят от сезона и фермера</span></div>
  <div class="разделы">{"".join(ряды)}</div>
</div></section>

<section><div class="обёртка">
  <div class="заг"><h2>На этой неделе</h2><span>привозим в четверг, 27 августа</span>
    <div class="фильтры">
      <button aria-pressed="true" data-метка="">Всё</button>
      <button aria-pressed="false" data-метка="товар дня">Товар дня</button>
      <button aria-pressed="false" data-метка="новинка">Новинки</button>
    </div></div>
  <div class="товары">{"".join(карточки)}</div>
  <p class="оффер">По четвергам доставим бесплатно при заказе от 5000 ₽ —
     это две форели или недельный набор молочного.</p>
  <p class="сноска">Цены указаны в информационных целях и не являются публичной офертой:
     они меняются от сезонности продукта и отдалённости фермера.</p>
</div></section>

<section class="тьма" id="как">{гравюра}<div class="обёртка">
  <div class="заг"><h2>Как это работает</h2></div>
  <div class="шаги">{шаги}</div>
  <div class="правила">
    <p><b>Охлаждённое — до среды.</b> Приём заказов закрывается за сутки до поставки,
       до 13:00: всё вылавливается и коптится специально для вас.</p>
    <p><b>В другие дни — экспресс.</b> Доставка за 2–3 часа после заказа,
       500 ₽ по городу независимо от суммы.</p>
    <p><b>По четвергам от 5000 ₽ — бесплатно.</b> Иначе 400 ₽ по Воронежу,
       Нововоронеж и Липецк — 450 ₽.</p>
    <p><b>Оплата при получении.</b> Наличными или картой курьеру, в лавке — картой
       или наличными. Предоплату не берём.</p>
  </div>
  <div class="график">{график}</div>
</div></section>

<section><div class="обёртка">
  <p class="гарантия">Нас заказывают Сбербанк, РЖД, МегаФон и Росэнергоатом —
     туда, где на угощении экономить не принято.</p>
  <p>Корпоративные поставки к праздникам и на мероприятия: соберём набор,
     привезём в офис, сделаем документы. Спросите по телефону
     <b>+7 929 009-50-55</b>.</p>
  <div class="заказчики">{заказчики}</div>
  <p>А ещё {словами} — и десятки компаний поменьше.</p>
</div></section>

<section class="бел"><div class="обёртка">
  <div class="заг"><h2>Как выбрать и приготовить</h2>
    <span>наши памятки — их пишем сами, а не переписываем из интернета</span></div>
  <div class="советы">{советы}</div>
</div></section>

<section id="фермеры"><div class="обёртка">
  <div class="заг"><h2>Наши фермеры</h2><span>к каждому съездили и всё попробовали сами</span></div>
  <div class="герой">
    <div class="вензель">{ГЕРОЙ['вензель']}</div>
    <div>
      <h3>{ГЕРОЙ['имя']}</h3>
      <div class="где">{ГЕРОЙ['где']} · {ГЕРОЙ['позиций']} позиции на сайте</div>
      <p>{ГЕРОЙ['текст']}</p>
      <div class="ещё">Рассказываем по очереди о каждом, у кого закупаемся.</div>
    </div>
  </div>
  <div class="фермеры">{ферм}</div>
</div></section>

<section><div class="обёртка">
  <p class="гарантия">Не понравился продукт — заменим или вернём деньги.
     Разберёмся с производителем сами.</p>
  <p>Это правило работает с 2010 года и записано у нас на странице «О нас».
     Пробовать новое не страшно.</p>
  <form class="подписка" onsubmit="event.preventDefault();
      this.querySelector('.готово').textContent='Подписали — напишем, когда назначим поставку.';">
    <input type="tel" placeholder="Телефон для смс о поставке"
           aria-label="Телефон для смс о ближайшей поставке" required>
    <button class="кнопка" type="submit">Подписаться</button>
    <div class="готово" style="color:var(--зелень);flex-basis:100%"></div>
  </form>
</div></section>

<section class="бел"><div class="обёртка">
  <div class="заг"><h2>Что о нас говорят</h2></div>
  <div class="отзывы">{отз}</div>
</div></section>

<section id="лавки"><div class="обёртка">
  <div class="заг"><h2 id="где-забрать">Лавки в Воронеже</h2>
    <span>заказы операторы принимают с 9:00 до 19:00, пн–пт</span></div>
  <p class="переезд"><b>Филиал с Перевёрткина, 24 переехал.</b> Ждём вас на
     улице Старых Большевиков, 2 — телефон прежний, +7 929 009-50-23.</p>
  <table><thead><tr><th>Адрес</th><th>Часы</th><th>Телефон</th></tr></thead>
  <tbody>{лавки}</tbody></table>
  <p class="сноска" id="другой-город" hidden>Адреса и телефоны в этом городе
     подставим, когда вы их пришлёте, — на старом сайте они открываются только
     после переключения города. Пока что заказ по телефону
     <b>+7 929 009-50-55</b>.</p>
</div></section>

<section class="заявка" id="заявка"><div class="обёртка">
  <div>
    <h2>Оставьте заявку</h2>
    <p>Перезвоним в рабочее время, подскажем, что из свежего приедет в четверг,
       и поможем выбрать. Можно просто позвонить: <b>+7 929 009-50-55</b>.</p>
  </div>
  <form onsubmit="event.preventDefault();this.querySelector('.готово').textContent=
      'Заявка принята — перезвоним в рабочее время.';">
    <input type="text" placeholder="Как вас зовут" aria-label="Как вас зовут" required>
    <input type="tel" placeholder="Телефон" aria-label="Телефон" required>
    <textarea placeholder="Что нужно привезти" aria-label="Что нужно привезти"></textarea>
    <button class="кнопка" type="submit">Отправить заявку</button>
    <small>Нажимая кнопку, вы соглашаетесь на обработку персональных данных.</small>
    <div class="готово"></div>
  </form>
</div></section>

<a class="кнопка липкая" href="#заявка">Заказать к четвергу</a>

<footer><div class="обёртка">
  <div>{подвал_лого}«Папина лавка» · натуральные продукты с доставкой, Воронеж<br>
     ИП Папин М.А., ОГРН 310366828700143</div>
  <div>+7 929 009-50-55 · papinalavka@gmail.com</div>
</div></footer>

<script>
const ГОРОДОВ = {всего_городов};

// Город меняет заголовок раздела с лавками. Адреса других городов на старом
// сайте открываются только после переключения, в выгрузку они не попали —
// поэтому вместо выдуманных адресов честная строка о том, что их подставят.
document.getElementById("город").addEventListener("change", e => {{
  const выбран = e.target.selectedOptions[0];
  const свой = e.target.value === "Воронеж";
  document.getElementById("где-забрать").textContent =
    `Лавки в ${{выбран.dataset.где}}`;
  document.querySelector("#лавки table").hidden = !свой;
  document.getElementById("другой-город").hidden = свой;
  // Цифра в полосе обязана совпадать с выбранным городом: «6 лавок в
  // Воронеже» при выбранном Липецке — это ровно та мелочь, из-за которой
  // клиент перестаёт верить остальным цифрам. Сколько точек в других
  // городах, мы не знаем, поэтому там честная цифра городов доставки.
  document.getElementById("плитка-лавок").innerHTML = свой
    ? "<b>6</b><span>лавок в Воронеже</span>"
    : `<b>${{ГОРОДОВ}}</b><span>городов доставки</span>`;
}});

// Счётчик до закрытия заказа. Срок не выдуман: по их правилам приём заказов на
// охлаждённое закрывается в среду в 13:00, за сутки до четверговой поставки.
// Это и есть причина заказать сегодня, а не «когда-нибудь».
function досреды() {{
  const сейчас = new Date();
  const срок = new Date(сейчас);
  // 3 — среда. Ищем ближайшую среду, 13:00 по местному времени покупателя.
  срок.setDate(сейчас.getDate() + ((3 - сейчас.getDay() + 7) % 7));
  срок.setHours(13, 0, 0, 0);
  if (срок <= сейчас) срок.setDate(срок.getDate() + 7);
  const минут = Math.floor((срок - сейчас) / 60000);
  const д = Math.floor(минут / 1440), ч = Math.floor((минут % 1440) / 60), м = минут % 60;
  const слово = (n, о, а, ов) => {{
    const s = Math.abs(n) % 100, b = s % 10;
    if (s > 10 && s < 20) return ов;
    if (b > 1 && b < 5) return а;
    return b === 1 ? о : ов;
  }};
  return д > 0 ? `${{д}} ${{слово(д, "день", "дня", "дней")}} ${{ч}} ${{слово(ч, "час", "часа", "часов")}}`
               : `${{ч}} ${{слово(ч, "час", "часа", "часов")}} ${{м}} ${{слово(м, "минута", "минуты", "минут")}}`;
}}
// Липкая кнопка появляется, когда своя кнопка первого экрана ушла вверх:
// две одинаковые кнопки на одном экране выглядят суетой.
const липкая = document.querySelector(".липкая");
addEventListener("scroll", () => липкая.classList.toggle("видна", scrollY > 620),
                 {{passive:true}});

const счётчик = document.getElementById("осталось");
const тик = () => {{ счётчик.textContent = досреды(); }};
тик();
setInterval(тик, 30000);

// Деления витрины у них на сайте есть («новинки», «хиты», «товар дня»), и в
// макете они работают: кнопка, которая ничего не делает, злит сильнее, чем её
// отсутствие.
document.querySelectorAll(".фильтры button").forEach(кнопка => {{
  кнопка.addEventListener("click", () => {{
    document.querySelectorAll(".фильтры button").forEach(
      к => к.setAttribute("aria-pressed", String(к === кнопка)));
    const метка = кнопка.dataset.метка;
    document.querySelectorAll(".товар").forEach(карточка => {{
      карточка.hidden = Boolean(метка) && карточка.dataset.метка !== метка;
    }});
  }});
}});

// Доска поставок сжимается при прокрутке: дата и срок заказа должны остаться
// на экране всё время, а место занимать перестать.
const доска = document.getElementById("доска");
const гравюра = document.querySelector(".гравюра");
addEventListener("scroll", () => {{
  доска.classList.toggle("сжата", scrollY > 120);
  // Параллакс считаем от положения самой полосы, а не от общей прокрутки:
  // иначе гравюра уезжает из блока задолго до того, как её увидят.
  if (гравюра) {{
    const полоса = гравюра.parentElement.getBoundingClientRect();
    const доля = Math.max(-1, Math.min(1, (innerHeight / 2 - polosaCenter(полоса)) / innerHeight));
    гравюра.style.transform = `translateY(${{доля * 26}}px)`;
  }}
}}, {{passive:true}});
function polosaCenter(r) {{ return r.top + r.height / 2; }}
</script>
</body></html>"""


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    куда = args[0] if args else os.path.join(ЗДЕСЬ, "index.html")
    for имя in ПАЛИТРЫ:
        if f"--{имя}" in sys.argv:
            ПАЛИТРА[0] = имя
    if "--файлами" in sys.argv:
        РЯДОМ["папка"] = os.path.dirname(os.path.abspath(куда))
    html = собрать()
    open(куда, "w", encoding="utf-8").write(html)
    вес = len(html.encode("utf-8")) / 1048576
    где = " + картинки в img/ рядом" if РЯДОМ["папка"] else " (картинки внутри файла)"
    print(f"Макет собран: {куда} — {вес:.1f} МБ{где}")
