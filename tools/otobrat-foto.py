#!/usr/bin/env python3
"""Отбор фотографий из выгрузки под готовые места в прототипе.

В прототипе шестнадцать мест под фотографии, и имена файлов в коде уже
заданы. Руками искать их среди трёх тысяч картинок бессмысленно: имена на
CDN конструктора ни о чём не говорят, а половина файлов — иконки шаблона.

Здесь это делается по двум признакам, которые известны из разбора:

1. **Какой странице принадлежит картинка.** Галерея «угловых кухонь» лежит
   на странице угловых кухонь, и только на ней: 2559 картинок из 3005
   встречаются ровно на одной странице. Значит, для каждого места в макете
   можно назвать страницу-источник.
2. **Вес файла.** Средний файл 72 КБ при медиане 32 — то есть мелочь это
   иконки шаблона, а настоящие фотографии работ тяжёлые. Внутри страницы
   берём самые крупные.

Запуск на сервере сканера, из /root/site-scanner-main:

    python3 tools/otobrat-foto.py /tmp/mebel-ryazane.ru.zip \
        clients/mebel-ryazane.ru/full clients/mebel-ryazane.ru/foto

Скрипт печатает, что выбрал и почему, — выбор проверяется глазами до показа
клиенту.
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

from bs4 import BeautifulSoup

# Место в макете → страница выгрузки, откуда берём кадр. Порядок важен:
# первые четыре — крупные места, дальше сетка работ.
MESTA: list[tuple[str, str, str, str]] = [
    ("kuhnya-uglovaya-01.jpg", "kuhni-uglovyie.html", "uglov", "первый экран, угловая кухня"),
    ("kuhnya-pryamaya-01.jpg", "kuhni-pryamyie.html", "pryam", "блок «Кухни»"),
    ("shkaf-kupe-01.jpg", "vstroennie-shkafi-kupe.html", "shkaf", "блок «Шкафы-купе»"),
    ("garderobnaya-01.jpg", "garderobnaya-iz-kladovki.html", "garderob", "блок «Гардеробные»"),
    ("rabota-01.jpg", "kuhni-belyie.html", "bel", "работы: белая кухня"),
    ("rabota-02.jpg", "kuhni-s-ostrovom.html", "ostrov", "работы: кухня с островом"),
    ("rabota-03.jpg", "kuhni-zelenyie.html", "zelen", "работы: зелёная кухня"),
    ("rabota-04.jpg", "kuhni-loft.html", "loft", "работы: кухня лофт"),
    ("rabota-05.jpg", "kuhnya-hruschevke.html", "hrusch", "работы: маленькая кухня"),
    ("rabota-06.jpg", "shkaf-kupe-zerkalom.html", "zerkal", "работы: шкаф с зеркалом"),
    ("rabota-07.jpg", "shkafi-kupe-prikhozhuyu.html", "prihozh", "работы: шкаф в прихожую"),
    ("rabota-08.jpg", "shkaf-pod-lestnitsei.html", "lestnits", "работы: шкаф под лестницей"),
    ("rabota-09.jpg", "bolshaya-garderobnaya.html", "garderob", "работы: гардеробная"),
    ("rabota-10.jpg", "prikhozhaya.html", "prihozh", "работы: прихожая"),
    ("rabota-11.jpg", "detskaya-mebel.html", "detsk", "работы: детская"),
    ("rabota-12.jpg", "vannaya.html", "vann", "работы: мебель для ванной"),
]

# Имена файлов на конструкторе говорящие: `kuhnya-s-ostrovom.jpg` — это
# кухня, а `fon_IiQJSaZ.jpg` — подложка секции, и по весу они не отличаются.
# Поэтому вес — второй признак, а первый — само имя.
NE_FOTO = ("fon", "bg", "background", "icon", "ikon", "el", "logo", "knopk",
           "button", "strelk", "arrow", "banner", "shapka", "header", "line")

IMG_ATTRS = ("data-src", "data-original", "data-lazy-src", "data-lazy",
             "data-echo", "data-image", "data-bg", "data-background")
CSS_URL = re.compile(r"""url\(\s*['"]?([^'")]+)['"]?\s*\)""", re.I)
# Только настоящие фотоформаты: png на конструкторе — это иконки и подложки,
# а имя файла в макете заканчивается на .jpg.
FOTO_EXT = (".jpg", ".jpeg")


def adresa_stranicy(html: str) -> set[str]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[str] = []
    for el in soup.find_all(["img", "source"]):
        out.append((el.get("src") or "").strip())
        for attr in IMG_ATTRS:
            out.append((el.get(attr) or "").strip())
        for attr in ("srcset", "data-srcset"):
            for part in (el.get(attr) or "").split(","):
                out.append(part.strip().split(" ")[0].strip())
    for el in soup.find_all(attrs={"style": True}):
        out += [m.group(1) for m in CSS_URL.finditer(el["style"])]
    adresa = set()
    for v in out:
        if not v or v.startswith(("data:", "javascript:", "#")):
            continue
        u = urljoin("https://mebel-ryazane.ru/", v).split("#")[0]
        if urlparse(u).path.lower().endswith(FOTO_EXT):
            adresa.add(u)
    return adresa


# Та же чистка имён, что в scanner/mirror.py: без неё путь не совпадёт с тем,
# под которым файл лежит в архиве.
_PLOHO = re.compile(r"[^\w.\-]+", re.U)


def put_v_arhive(url: str) -> str:
    """Как обход назвал файл внутри архива: `_vneshnie/<хост>/<путь>`."""
    p = urlparse(url)
    host = _PLOHO.sub("_", p.netloc.lower())
    segments = [_PLOHO.sub("_", unquote(s))[:120] or "_"
                for s in p.path.split("/") if s not in ("", ".", "..")]
    return f"_vneshnie/{host}/" + "/".join(segments)


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(__doc__)
        return 2
    arhiv, stranicy, kuda = Path(argv[1]), Path(argv[2]), Path(argv[3])
    for p in (arhiv, stranicy):
        if not p.exists():
            print(f"нет такого пути: {p}")
            return 2
    kuda.mkdir(parents=True, exist_ok=True)

    # Считаем, на скольких страницах встречается каждый адрес: то, что стоит
    # на всех, — шаблон, а не работа клиента.
    vstrechaetsya: dict[str, int] = {}
    po_stranicam: dict[str, set[str]] = {}
    for f in sorted(stranicy.glob("*.html")):
        adresa = adresa_stranicy(f.read_text(encoding="utf-8", errors="replace"))
        po_stranicam[f.name] = adresa
        for a in adresa:
            vstrechaetsya[a] = vstrechaetsya.get(a, 0) + 1

    with zipfile.ZipFile(arhiv) as zf:
        vnutri = {i.filename: i.file_size for i in zf.infolist()}
        vzyato: set[str] = set()
        ne_nashlos: list[str] = []

        for imya, stranica, slovo, zachem in MESTA:
            adresa = po_stranicam.get(stranica)
            if adresa is None:
                ne_nashlos.append(f"{imya}: нет страницы {stranica}")
                continue
            # Кандидаты: только свои для этой страницы и ещё не занятые.
            kandidaty = []
            for a in adresa:
                # Порог 40, а не «только своя»: у двенадцати страниц
                # гардеробных галерея общая, и строгий фильтр оставлял их
                # без единого кадра. Шаблон сайта — это 70+ страниц.
                if vstrechaetsya.get(a, 0) > 40 or a in vzyato:
                    continue
                put = put_v_arhive(a)
                if put not in vnutri:
                    continue
                fayl = put.rsplit("/", 1)[-1].lower()
                if any(fayl.startswith(x) for x in NE_FOTO):
                    continue
                kandidaty.append((1 if slovo in fayl else 0, vnutri[put], put, a))
            if not kandidaty:
                ne_nashlos.append(f"{imya}: на странице {stranica} не нашлось своих фотографий")
                continue
            # Сначала имя по делу, потом вес: крупный кадр среди подходящих.
            kandidaty.sort(reverse=True)
            po_imeni, ves, put, adres = kandidaty[0]
            vzyato.add(adres)
            (kuda / imya).write_bytes(zf.read(put))
            print(f"{imya:26} {ves/1024:6.0f} КБ  ← {stranica}"
                  f"{'  (имя по делу)' if po_imeni else '  (только по весу — проверить)'}\n"
                  f"{'':26} {zachem}\n"
                  f"{'':26} {adres}")

    print(f"\nПоложено в {kuda}: {len(list(kuda.glob('*.jpg')))} файлов")
    if ne_nashlos:
        print("\nНе нашлось:")
        for x in ne_nashlos:
            print(f"  {x}")
    print("\nПосмотрите глазами: кадр с людьми, тёмный или обрезанный — заменить"
          " соседним из той же страницы.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
