#!/usr/bin/env python3
"""Отбор фотографий из выгрузки под готовые места в прототипе.

В прототипе шестнадцать мест под фотографии, и имена файлов в коде уже
заданы. Руками искать их среди трёх тысяч картинок бессмысленно: имена на
CDN конструктора ни о чём не говорят, а половина файлов — иконки шаблона.

Отбор идёт по четырём признакам, и три последних появились после того, как
первый заход привёз пять негодных кадров из шестнадцати:

1. **Какой странице принадлежит картинка.** Галерея «угловых кухонь» лежит
   на странице угловых кухонь, и только на ней: 2559 картинок из 3005
   встречаются ровно на одной странице. Значит, для каждого места в макете
   можно назвать страницы-источники.
2. **Размер кадра.** Решающий признак, которого не хватало. Вес не отличает
   фотографию от карточки с нарисованной иконкой: обе по 40 КБ. А размер
   отличает — настоящие снимки работ в этой выгрузке от 830 пикселей по
   ширине, карточки ровно 457×508, баннеры-полосы 1921×717. Поэтому кадр уже
   `MIN_SHIRINA` и всё, что не похоже по пропорциям на фотографию комнаты,
   выбывает до взвешивания.
3. **Имя файла.** На конструкторе имена говорящие, и брак называет себя сам:
   `raschet-kuhni-1.jpg` — баннер с калькулятором, `napolnenie-shkafa` —
   схема с размерами. Отдельный список `NE_FOTO` их отсекает.
4. **Вес файла.** Последний признак, а не первый: среди прошедших фильтры
   крупный файл действительно означает более чистый кадр.

Два режима. Обычный кладёт по одному файлу на место:

    python3 tools/otobrat-foto.py /tmp/mebel.zip \\
        clients/mebel-ryazane.ru/full clients/mebel-ryazane.ru/foto

С `--kandidaty N` кладёт по N штук на место, в подпапки. Это режим для
разбора: кадры смотрятся глазами разом, а не по одному за заход владельца.
Автоматика отличает фотографию от схемы, но не отличает **фотографию работы
от 3D-визуализации и каталожного кадра чужой фабрики** — а на сайте клиента
это разные вещи, и решать должен человек.

    python3 tools/otobrat-foto.py /tmp/mebel.zip \\
        clients/mebel-ryazane.ru/full clients/mebel-ryazane.ru/kandidaty \\
        --kandidaty 6

Скрипт печатает, что выбрал и почему, — выбор проверяется глазами до показа
клиенту.
"""

from __future__ import annotations

import re
import struct
import sys
import zipfile
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

try:
    from bs4 import BeautifulSoup
except ImportError:                       # на хосте сервера его может не быть
    BeautifulSoup = None

# Место в макете → страницы выгрузки, откуда берём кадр. Страниц несколько, а
# не одна: у страницы бывает галерея из схем и баннеров, и тогда своих
# фотографий на ней просто нет — так место «гардеробная» в первом заходе
# получило баннер с калькулятором. Соседняя страница той же услуги закрывает
# дыру, оставаясь по смыслу тем же самым.
#
# **Категории берутся из прототипа, а не из головы.** В `src/routes/index.tsx`
# у каждой карточки сетки работ жёстко заданы `category` и `alt`: rabota-01..04
# — «Кухни», 05..07 — «Шкафы-купе», 08..09 — «Гардеробные», 10 — «Прихожие»,
# 11 — «Детская», 12 — «Ванная». Раскладка обязана им соответствовать: иначе
# фотография кухни встаёт под фильтр «Шкафы-купе» и с подписью про шкаф —
# ошибка, которую видно и глазами, и поиску. Проверено на живом: первая
# раскладка ставила в 05 маленькую кухню, а в 08 шкаф под лестницей.
#
# Страницы-источники выбраны по числу собственных картинок, а не наугад:
# у гардеробных настоящая галерея одна — `garderobnaya-prikhozhei.html`
# (31 снимок), а на остальных двенадцати страницах лежат схемы и общий шаблон.
# Отсюда и был пустой результат: список источников назвал не ту страницу.
MESTA: list[tuple[str, tuple[str, ...], str, str]] = [
    ("kuhnya-uglovaya-01.jpg", ("kuhni-uglovyie.html", "kuhni-sovremennyie.html"),
     "uglov", "первый экран, угловая кухня"),
    ("kuhnya-pryamaya-01.jpg", ("kuhni-pryamyie.html", "kuhni-sovremennyie.html"),
     "pryam", "блок «Кухни»"),
    ("shkaf-kupe-01.jpg", ("vstroennie-shkafi-kupe.html", "shkafi-kupe-spalnyu.html",
                           "sovremennie-shkafi.html"),
     "shkaf", "блок «Шкафы-купе»"),
    ("garderobnaya-01.jpg", ("garderobnaya-prikhozhei.html", "garderobnaya-komnata.html",
                             "uglovaya-garderobnaya.html"),
     "garderob", "блок «Гардеробные»"),
    ("rabota-01.jpg", ("kuhni-belyie.html",), "bel", "работы, Кухни: белая"),
    ("rabota-02.jpg", ("kuhni-s-ostrovom.html",), "ostrov", "работы, Кухни: с островом"),
    ("rabota-03.jpg", ("kuhni-zelenyie.html",), "zelen", "работы, Кухни: зелёная"),
    ("rabota-04.jpg", ("kuhni-loft.html",), "loft", "работы, Кухни: лофт"),
    ("rabota-05.jpg", ("shkaf-pod-lestnitsei.html", "uglovoi-shkaf-kupe.html",
                       "shkaf-kupe-koridor.html"),
     "shkaf", "работы, Шкафы-купе: встроенный"),
    ("rabota-06.jpg", ("shkaf-kupe-zerkalom.html",), "zerkal",
     "работы, Шкафы-купе: с зеркалом"),
    ("rabota-07.jpg", ("shkafi-kupe-prikhozhuyu.html",), "prihozh",
     "работы, Шкафы-купе: в прихожую"),
    ("rabota-08.jpg", ("garderobnaya-prikhozhei.html",), "garderob",
     "работы, Гардеробные: в прихожей"),
    ("rabota-09.jpg", ("garderobnaya-prikhozhei.html", "vstroennaya-garderobnaya.html"),
     "garderob", "работы, Гардеробные: встроенная"),
    ("rabota-10.jpg", ("prikhozhaya.html",), "prihozh", "работы: прихожая"),
    ("rabota-11.jpg", ("shkafi-kupe-detskuyu.html", "detskaya-mebel.html"),
     "detsk", "работы: детская"),
    ("rabota-12.jpg", ("shkaf-kupe-vannuyu.html", "vannaya.html"),
     "vann", "работы: мебель для ванной"),
]

# Имена файлов на конструкторе говорящие: `kuhnya-s-ostrovom.jpg` — это
# кухня, а `fon_IiQJSaZ.jpg` — подложка секции, и по весу они не отличаются.
#
# Сравниваем **по частям имени**, а не по вхождению подстроки, и это не
# придирка к стилю. Короткий маркер `el` (от «element») внутри строки попадает
# в `belaya` и `zelenaya`: заход с проверкой `in` выбросил белую и зелёную
# кухни — оба кадра годные — и оставил три места вовсе без кандидатов.
# Имя рубится по `-`, `_` и точке, дальше часть сравнивается целиком либо по
# началу.
NE_FOTO_TOCHNO = frozenset((
    "el", "bg", "fon", "line", "icon", "ikon", "logo", "banner", "header",
    "arrow", "button", "color", "fill", "dizajner",
))
# Здесь начало части: «aktsiya» и «aktsii», «shemy» и «shema» — одно и то же.
# Всё, что тут перечислено, — брак, вскрытый первым заходом: баннер расчёта с
# калькулятором приехал вместо гардеробной, схема наполнения с размерами —
# вместо фотографии шкафа.
NE_FOTO_NACHALO = (
    "background", "knopk", "strelk", "shapka", "raschet", "kalkulyator",
    "kupon", "aktsi", "skidk", "podarok", "shema", "sxema", "chertezh",
    "napolnenie", "razmer", "zamer", "otziv", "sertifikat", "dostavka",
    "oplata", "garantiya",
)
_CHASTI = re.compile(r"[-_.]+")


def imya_brakovannoe(fayl: str) -> bool:
    for chast in _CHASTI.split(fayl.lower()):
        if not chast:
            continue
        if chast in NE_FOTO_TOCHNO or chast.startswith(NE_FOTO_NACHALO):
            return True
    return False

IMG_ATTRS = ("data-src", "data-original", "data-lazy-src", "data-lazy",
             "data-echo", "data-image", "data-bg", "data-background")
CSS_URL = re.compile(r"""url\(\s*['"]?([^'")]+)['"]?\s*\)""", re.I)
# Только настоящие фотоформаты: png на конструкторе — это иконки и подложки,
# а имя файла в макете заканчивается на .jpg.
FOTO_EXT = (".jpg", ".jpeg")

# Пороги отбраковки по кадру. Взяты не из головы, а из первого захода:
# карточки услуг на сайте ровно 457×508, и по весу (40 КБ) они не отличались
# от настоящих фотографий, поэтому две такие и приехали — с нарисованной
# поверх кадра иконкой «палец нажимает». Настоящие снимки работ здесь
# начинаются от 830 пикселей.
MIN_SHIRINA = 700
# Полоса-баннер во всю ширину экрана (1921×717 — сток с ребёнком на кровати,
# мебели в кадре нет вовсе) и вертикальная карточка отсекаются пропорциями:
# фотография комнаты почти всегда между квадратом и широким кадром.
MIN_OTNOSHENIE, MAX_OTNOSHENIE = 1.05, 2.10
# Заливка цвета и однотонная подложка проходят и по размеру, и по пропорциям:
# `color-fill-1-2.jpg` — 1920×1010 при 23 КБ. Отличает их плотность: у неё
# 0,012 байта на пиксель, у настоящей фотографии от 0,06. Порог с запасом.
MIN_PLOTNOST = 0.03


# Запасной разбор без BeautifulSoup: на сервере сканера скрипт запускается на
# хосте (репозиторий в контейнер не копируется), а bs4 там ставить незачем ради
# одной команды. Адреса на конструкторе протокол-относительные — `//media...`,
# поэтому схема в выражении необязательна.
_ADRESA = re.compile(
    r"""(?:src|data-src|data-original|data-lazy-src|srcset|data-srcset)\s*=\s*["']([^"']+)["']"""
    r"""|url\(\s*['"]?([^'")]+)['"]?\s*\)""", re.I)


def adresa_regexpom(html: str) -> list[str]:
    out: list[str] = []
    for m in _ADRESA.finditer(html):
        znachenie = m.group(1) or m.group(2) or ""
        # srcset — это «адрес 1x, адрес 2x»: дескрипторы отбрасываем
        for chast in znachenie.split(","):
            out.append(chast.strip().split(" ")[0].strip())
    return out


def adresa_stranicy(html: str) -> set[str]:
    if BeautifulSoup is None:
        adresa = set()
        for v in adresa_regexpom(html):
            if not v or v.startswith(("data:", "javascript:", "#")):
                continue
            u = urljoin("https://mebel-ryazane.ru/", v).split("#")[0]
            if urlparse(u).path.lower().endswith(FOTO_EXT):
                adresa.add(u)
        return adresa

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


# Размер кадра из заголовка JPEG. Своими руками, а не Pillow: на хосте сервера
# его нет, а ставить зависимость ради двух чисел незачем — маркер SOF лежит в
# первых килобайтах файла.
_SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
        0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def razmer_jpeg(nachalo: bytes) -> tuple[int, int]:
    """(ширина, высота) или (0, 0), если заголовок не разобрался."""
    if not nachalo.startswith(b"\xff\xd8"):
        return 0, 0
    i = 2
    while i + 9 < len(nachalo):
        if nachalo[i] != 0xFF:
            i += 1
            continue
        marker = nachalo[i + 1]
        if marker in _SOF:
            h, w = struct.unpack(">HH", nachalo[i + 5:i + 9])
            return w, h
        if marker == 0xD8 or marker == 0xD9 or 0xD0 <= marker <= 0xD7 or marker == 0xFF:
            i += 2
            continue
        dlina = struct.unpack(">H", nachalo[i + 2:i + 4])[0]
        if dlina < 2:
            return 0, 0
        i += 2 + dlina
    return 0, 0


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


def kadr_goditsya(zf: zipfile.ZipFile, put: str, ves: int) -> tuple[bool, int, int]:
    """Похоже ли содержимое на фотографию работы, а не на карточку или полосу."""
    try:
        with zf.open(put) as f:
            w, h = razmer_jpeg(f.read(65536))
    except (KeyError, OSError):
        return False, 0, 0
    if not w or not h:
        return False, w, h
    if w < MIN_SHIRINA:
        return False, w, h
    if not MIN_OTNOSHENIE <= w / h <= MAX_OTNOSHENIE:
        return False, w, h
    return ves / (w * h) >= MIN_PLOTNOST, w, h


def main(argv: list[str]) -> int:
    argv = list(argv)
    skolko = 1
    if "--kandidaty" in argv:
        i = argv.index("--kandidaty")
        try:
            skolko = int(argv[i + 1])
        except (IndexError, ValueError):
            print("--kandidaty ждёт число")
            return 2
        del argv[i:i + 2]
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
        otbrakovano = 0

        for imya, stranicy_mesta, slovo, zachem in MESTA:
            kandidaty = []
            # Страниц-источников несколько, и одна картинка лежит сразу на
            # нескольких: без этого набора `shkaf-kupevivatv` приезжал в папку
            # трижды и съедал места под живые варианты.
            uzhe_v_meste: set[str] = set()
            for nomer_stranicy, stranica in enumerate(stranicy_mesta):
                adresa = po_stranicam.get(stranica)
                if adresa is None:
                    ne_nashlos.append(f"{imya}: нет страницы {stranica}")
                    continue
                for a in adresa:
                    # Порог 40, а не «только своя»: у двенадцати страниц
                    # гардеробных галерея общая, и строгий фильтр оставлял их
                    # без единого кадра. Шаблон сайта — это 70+ страниц.
                    if vstrechaetsya.get(a, 0) > 40 or a in vzyato:
                        continue
                    put = put_v_arhive(a)
                    if put not in vnutri or put in uzhe_v_meste:
                        continue
                    fayl = put.rsplit("/", 1)[-1].lower()
                    if imya_brakovannoe(fayl):
                        continue
                    godno, w, h = kadr_goditsya(zf, put, vnutri[put])
                    if not godno:
                        otbrakovano += 1
                        continue
                    uzhe_v_meste.add(put)
                    # Порядок предпочтения: страница по смыслу ближе (первая в
                    # списке), потом имя по делу, потом вес.
                    kandidaty.append((-nomer_stranicy, 1 if slovo in fayl else 0,
                                      vnutri[put], put, a, w, h))
            if not kandidaty:
                ne_nashlos.append(
                    f"{imya}: на страницах {', '.join(stranicy_mesta)} не нашлось фотографий")
                continue
            kandidaty.sort(reverse=True)

            if skolko == 1:
                _, po_imeni, ves, put, adres, w, h = kandidaty[0]
                vzyato.add(adres)
                (kuda / imya).write_bytes(zf.read(put))
                print(f"{imya:26} {w}x{h}  {ves/1024:6.0f} КБ"
                      f"{'  (имя по делу)' if po_imeni else '  (только по весу — проверить)'}\n"
                      f"{'':26} {zachem}\n"
                      f"{'':26} {adres}")
                continue

            papka = kuda / imya.replace(".jpg", "")
            papka.mkdir(parents=True, exist_ok=True)
            print(f"\n{imya}  — {zachem}")
            for n, (_, po_imeni, ves, put, adres, w, h) in enumerate(kandidaty[:skolko], 1):
                vzyato.add(adres)
                (papka / f"{n:02d}.jpg").write_bytes(zf.read(put))
                print(f"   {n:02d}  {w}x{h}  {ves/1024:5.0f} КБ  "
                      f"{adres.rsplit('/', 1)[-1]}")

        vsego = len(list(kuda.rglob("*.jpg")))
        print(f"\nПоложено в {kuda}: {vsego} файлов")
        print(f"Отбраковано по размеру кадра: {otbrakovano} "
              f"(карточки 457×508, баннеры-полосы, схемы)")
    if ne_nashlos:
        print("\nНе нашлось:")
        for x in ne_nashlos:
            print(f"  {x}")
    print("\nПосмотрите глазами: кадр с людьми, тёмный или обрезанный — заменить"
          " соседним из той же страницы.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
