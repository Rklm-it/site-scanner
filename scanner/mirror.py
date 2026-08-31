"""Полная выгрузка сайта клиента в архив — для разбора перед переделкой.

Зачем свой обход, а не `wget --mirror`. Раньше выгрузку делали руками на
сервере, и каждый раз всплывало одно и то же:

* `wget` падал с `free(): invalid pointer` на этапе `--convert-links` —
  файлы уже скачаны, но команда выходит с ошибкой, и непонятно, целая
  выгрузка или нет;
* тянулись RSS/Atom-ленты (`?format=feed`) — на Joomla это десятки файлов,
  дубли каталога в XML, которые потом удаляли отдельной командой;
* старые сайты рунета отдают windows-1251, и `wget` сохраняет байты как
  есть. В репозитории такой файл читается как мусор, а разбор текстов —
  это главное, ради чего выгрузка и делается;
* `wget` в образе нет: python:3.12-slim идёт без него, а запускать внешнюю
  команду с доменом из веб-формы — лишняя дыра.

Здесь всё это решено на входе: ленты и тяжёлые файлы не скачиваются вовсе,
HTML перекодируется в UTF-8 готовым детектором из `fetcher`, а у обхода —
свой бюджет времени, как у остальных фаз прогона.

Итог кладётся одним zip-архивом плюс `manifest.json` с картой страниц:
по нему видно структуру сайта, не распаковывая архив.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import time
import zipfile
from typing import Callable
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .fetcher import DEFAULT_HEADERS
from .politeness import Politeness

log = logging.getLogger("scanner.mirror")

# Тяжёлое не тащим: архив уезжает в git-репозиторий, там ему не место.
# Список намеренно совпадает с правилами clients/** в .gitignore — чтобы
# скачанное не оказалось тем, что потом всё равно не закоммитить.
SKIP_EXT = {
    ".zip", ".rar", ".7z", ".gz", ".tar", ".pdf", ".doc", ".docx", ".xls",
    ".xlsx", ".ppt", ".pptx", ".mp4", ".avi", ".mov", ".wmv", ".mkv", ".mp3",
    ".wav", ".exe", ".msi", ".apk", ".iso", ".dmg", ".woff", ".woff2", ".ttf",
    ".eot", ".otf",
}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".bmp"}
ASSET_EXT = IMAGE_EXT | {".css", ".js"}
# Служебные ветки CMS: там нет содержимого, ради которого затевается разбор,
# зато обход в них уходит охотно и тратит бюджет.
SKIP_PATH = re.compile(
    r"/(administrator|wp-admin|wp-login|bitrix|admin|login|logout|cart|basket"
    r"|korzina|search|component/(search|users)|index\.php/component)",
    re.I,
)
_CSS_URL = re.compile(r"""url\(\s*['"]?([^'")]+)['"]?\s*\)""", re.I)
# Адрес картинки лежит в `src` далеко не всегда: ленивая загрузка держит его в
# `data-src`, ретина — в `srcset`, фон секции — в `style="background:url(...)"`,
# а часть оформления живёт в `<style>` прямо на странице. Пока смотрели только
# `src`, выгрузка мебельного сайта приезжала с нулём файлов — то есть без
# портфолио, ради которого её и делают.
_IMG_ATTRS = ("data-src", "data-original", "data-lazy-src", "data-lazy",
              "data-echo", "data-image", "data-bg", "data-background")
_SRCSET_ATTRS = ("srcset", "data-srcset")
_BAD_SEG = re.compile(r"[^\w.\-]+", re.U)
_CHARSET_HDR = re.compile(r"charset=[\"']?([\w\-]+)", re.I)
_META_CHARSET = re.compile(rb"""charset=["']?([\w\-]+)""", re.I)
# Постраничная навигация каталога. Адреса с запросом мы вообще-то пропускаем
# (на Joomla по ним живут ленты и сортировки — тот же контент под другим
# адресом), но пагинация — исключение: за ней лежат товары, которых больше
# нигде нет. У projekt-doma.ru это `gotovye-proekty?start=60`, и без неё
# половина каталога в выгрузку не попадала.
_PAGING_Q = re.compile(r"^(start|page|limitstart|PAGEN_\d+)=\d+$", re.I)


def _keep_query(query: str) -> bool:
    """Пускать ли адрес с запросом. Только чистая пагинация, ничего больше."""
    return bool(query) and all(_PAGING_Q.match(p) for p in query.split("&") if p)


def _decode_page(raw: bytes, ctype: str, learned: str | None) -> tuple[str, str]:
    """HTML → текст. Возвращает (текст, применённая кодировка).

    Почему не общий `fetcher.detect_encoding`: он на неопределившемся случае
    зовёт автодетектор, а тот врёт на коротких страницах. Проверено на живом
    примере — главная в windows-1251 определялась верно, а карточка товара из
    двух строк уезжала в японскую кодировку, и в разбор попадал мусор вида
    «ﾄ黑 1» вместо «Дом 1». Для выгрузки, которая делается ровно ради текстов,
    это провал.

    Порядок такой:

    1. Явное объявление — заголовок HTTP или `<meta charset>`. Сказано прямо,
       спорить не с чем.
    2. Строгий utf-8. Он сам себе проверка: случайные байты windows-1251
       почти никогда не складываются в корректную utf-8 последовательность,
       так что удачное декодирование — это и есть доказательство.
    3. Кодировка, уже определённая на этом сайте. Внутри одного сайта она
       не меняется, а главная обычно длинная и определяется надёжно.
    4. windows-1251 — самый частый вариант для старого рунета, и он
       декодирует что угодно без исключения, поэтому идёт последним.
    """
    m = _CHARSET_HDR.search(ctype or "")
    if not m:
        m = _META_CHARSET.search(raw[:4096])
    if m:
        enc = m.group(1)
        if isinstance(enc, bytes):
            enc = enc.decode("ascii", errors="ignore")
        try:
            return raw.decode(enc), enc.lower()
        except (UnicodeDecodeError, LookupError):
            pass

    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass

    for enc in (learned, "windows-1251"):
        if not enc or enc == "utf-8":
            continue
        try:
            return raw.decode(enc), enc
        except (UnicodeDecodeError, LookupError):
            continue

    return raw.decode("utf-8", errors="replace"), "utf-8"


@dataclass
class MirrorStats:
    """Что получилось — этим же наполняется прогресс-бар в интерфейсе."""

    pages: int = 0
    assets: int = 0
    bytes: int = 0
    skipped: int = 0
    # Сколько каких ответов пришло: {503: 400} сразу объясняет пустую выгрузку,
    # а без этого «страниц 0» одинаково выглядит и при заглушке антибота, и
    # при недоступном сайте — час уходит на выяснение, что именно.
    statuses: dict[int, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    pages_index: list[dict] = field(default_factory=list)
    archive: str | None = None
    stopped_by: str | None = None      # limit / deadline / bytes / disk / done
    # Сколько осталось в очередях, когда обход остановили. Без этих двух чисел
    # «выгрузка неполная» приходится вычислять руками по manifest.json, а
    # заметно это становится через неделю, когда сайт уже разобран не весь.
    pages_left: int = 0
    assets_left: int = 0
    # Почему файлов в выгрузке мало или нет вовсе. «Ни одной картинки» —
    # самая частая жалоба, и до сих пор причину выясняли запросами к живому
    # сайту; теперь она лежит в самом архиве: адреса картинок посчитаны, а
    # отказы разложены по причинам («чужой хост st.example.ru» и подобным).
    asset_refs: int = 0
    asset_skipped: dict[str, int] = field(default_factory=dict)
    assets_external: int = 0     # из них с чужих хостов — CDN конструктора


def _same_site(url: str, host: str) -> bool:
    """Свой ли это домен. www и голый вариант считаем одним сайтом,
    поддомены — чужими: на них обычно висит отдельный проект."""
    netloc = urlparse(url).netloc.lower().split(":")[0]
    host = host.lower()
    return netloc in (host, f"www.{host}") or (
        host.startswith("www.") and netloc == host[4:]
    )


def _ext(path: str) -> str:
    tail = path.rsplit("/", 1)[-1]
    return ("." + tail.rsplit(".", 1)[1].lower()) if "." in tail else ""


def _image_refs(soup) -> list[str]:
    """Адреса картинок, которых нет в обычном `src`.

    Разметку смотрим в четырёх местах: ленивые атрибуты и `srcset` у `<img>` и
    `<source>`, `url(...)` в атрибуте `style` у чего угодно и `url(...)` в
    `<style>` на самой странице. Внешние css-файлы разбираются отдельно, уже
    после скачивания.
    """
    out: list[str] = []
    for el in soup.find_all(["img", "source"]):
        for attr in _IMG_ATTRS:
            out.append((el.get(attr) or "").strip())
        for attr in _SRCSET_ATTRS:
            # `srcset` — это «адрес 1x, адрес 2x»: берём адреса, дескрипторы нет
            for part in (el.get(attr) or "").split(","):
                out.append(part.strip().split(" ")[0].strip())
        if el.name == "source":
            out.append((el.get("src") or "").strip())
    for el in soup.find_all(attrs={"style": True}):
        out += [m.group(1).strip() for m in _CSS_URL.finditer(el["style"])]
    for el in soup.find_all("style"):
        out += [m.group(1).strip() for m in _CSS_URL.finditer(el.get_text())]
    return [v for v in out if v and not v.startswith(("data:", "javascript:", "#"))]


def _local_path(url: str) -> str:
    """Адрес → путь внутри архива.

    Запрос (`?...`) в имя не попадает: на Joomla по нему живут ленты и
    сортировки, то есть тот же контент под другим адресом. Точки-сегменты
    вырезаются, иначе `..` в чужой ссылке увёл бы запись выше папки выгрузки.
    """
    parsed = urlparse(url)
    raw = [s for s in parsed.path.split("/") if s not in ("", ".", "..")]
    # Раскодировать %-последовательности ДО чистки имени. Иначе «410%201.jpg»
    # (то есть файл «410 1.jpg» с пробелом — на старых сайтах таких полно)
    # превращался в «410_201.jpg»: имя читается как число 201 и не совпадает
    # ни с чем на сайте. После unquote получается честное «410_1.jpg».
    segments = [_BAD_SEG.sub("_", unquote(s))[:120] or "_" for s in raw]
    if not segments:
        segments = ["index"] if _keep_query(parsed.query) else ["index.html"]
    if _ext(segments[-1]) in ASSET_EXT:
        return "/".join(segments)     # у картинок и стилей запрос в имя не идёт
    # Страница пагинации — иначе вторая страница каталога перезаписала бы первую
    if _keep_query(parsed.query):
        base = re.sub(r"\.html?$", "", segments[-1], flags=re.I)
        segments[-1] = f"{base}~{_BAD_SEG.sub('_', parsed.query)}"
    # Страница без расширения — доклеиваем .html, иначе файл не откроется
    if _ext(segments[-1]) not in (".html", ".htm"):
        segments[-1] += ".html"
    return "/".join(segments)


def _get(url: str, *, timeout: float, max_bytes: int,
         session: requests.Session) -> tuple[int, str, bytes, str] | None:
    """Скачивает один адрес. Возвращает (статус, content-type, тело, финальный
    адрес) либо None при ошибке.

    Тело читается чанками с потолком по объёму: `timeout` у requests считается
    на одну операцию с сокетом, и на медленной «струйке» байт одного его мало —
    та же причина, по которой в fetcher есть max_total.
    """
    resp = session.get(url, headers=DEFAULT_HEADERS, timeout=timeout,
                       allow_redirects=True, stream=True)
    try:
        buf = bytearray()
        for chunk in resp.iter_content(32768):
            if chunk:
                buf += chunk
            if len(buf) >= max_bytes:
                break
    finally:
        resp.close()
    ctype = resp.headers.get("content-type", "").lower()
    return resp.status_code, ctype, bytes(buf), resp.url


_LOC = re.compile(rb"<loc>\s*([^<\s]+)\s*</loc>", re.I)
_ROBOTS_SITEMAP = re.compile(r"^\s*sitemap:\s*(\S+)", re.I | re.M)


def _sitemap_urls(root: str, session: requests.Session, timeout: float,
                  limit: int) -> list[str]:
    """Адреса страниц из карты сайта.

    Обход идёт по ссылкам, а в меню попадает не всё: у блогов и каталогов
    половина страниц доступна только через пагинацию или вообще ниоткуда не
    прилинкована. Карта сайта перечисляет их явно — это самый дешёвый способ
    не пропустить содержимое, и делают её почти все CMS.

    Разбираем и индексные карты (карта из карт), но на один уровень вглубь:
    дальше начинаются многотысячные простыни новостных сайтов, а у нас на
    выгрузку есть бюджет.
    """
    seen: list[str] = []
    candidates = [urljoin(root, p) for p in
                  ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml", "/sitemap/sitemap.xml")]
    # robots.txt часто указывает карту прямо, включая нестандартные пути
    try:
        r = session.get(urljoin(root, "/robots.txt"), headers=DEFAULT_HEADERS, timeout=timeout)
        if r.status_code < 400:
            candidates += [m.strip() for m in _ROBOTS_SITEMAP.findall(r.text)]
    except requests.RequestException:
        pass

    queue = list(dict.fromkeys(candidates))
    nested_left = 1
    while queue and len(seen) < limit:
        url = queue.pop(0)
        try:
            r = session.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        except requests.RequestException:
            continue
        if r.status_code >= 400 or b"<loc" not in r.content[:200_000]:
            continue
        locs = [m.decode("utf-8", "replace") for m in _LOC.findall(r.content)]
        is_index = b"<sitemapindex" in r.content[:2000].lower()
        if is_index and nested_left > 0:
            nested_left -= 1
            queue += locs[:20]
            continue
        for loc in locs:
            if loc not in seen:
                seen.append(loc)
            if len(seen) >= limit:
                break
    if seen:
        log.info("Карта сайта: %d адресов", len(seen))
    return seen


def _pick_root(domain: str, session: requests.Session, timeout: float) -> str:
    """Выбирает рабочую схему для стартовой страницы.

    Сначала https, при неудаче — http. Это не перестраховка: у одного из лидов
    (`print-rf.ru`) сертификат выписан на чужое имя, и https не открывается
    вообще — с жёстко зашитым https выгрузка такого сайта вернула бы ноль
    страниц, а причина была бы неочевидна.
    """
    answered: str | None = None      # схема, которая хоть как-то ответила
    for scheme in ("https", "http"):
        url = f"{scheme}://{domain}/"
        try:
            resp = session.head(url, headers=DEFAULT_HEADERS, timeout=timeout,
                                allow_redirects=True)
            if resp.status_code < 400:
                return resp.url
            answered = answered or resp.url
        except requests.RequestException:
            continue
        # HEAD поддерживают не все старые сайты — пробуем обычным запросом
        try:
            resp = session.get(url, headers=DEFAULT_HEADERS, timeout=timeout,
                               allow_redirects=True, stream=True)
            resp.close()
            if resp.status_code < 400:
                return resp.url
            answered = answered or resp.url
        except requests.RequestException:
            continue
    # Никто не ответил успехом. Берём схему, которая хотя бы отозвалась: сайт
    # за антиботом отдаёт 503 по http и не слушает https, и с жёстким https
    # выгрузка заканчивалась SSL-ошибкой вместо честного «сайт отвечает
    # отказом» — причина видна совсем не та.
    return answered or f"https://{domain}/"


def run(
    domain: str,
    dest_dir: Path,
    *,
    max_pages: int = 1500,
    max_depth: int = 3,
    time_budget: float = 1800.0,
    assets_share: float = 0.4,
    per_host_delay: float = 0.7,
    respect_robots: bool = True,
    max_total_bytes: int = 200 * 1024 * 1024,
    max_file_bytes: int = 15 * 1024 * 1024,
    # Сколько места на диске оставить нетронутым. Выгрузка живёт на том же
    # томе, что база лидов и ключи: забить его фотографиями чужого сайта —
    # это не «неудачная выгрузка», а остановка всего инструмента.
    min_free_bytes: int = 0,
    timeout: float = 15.0,
    scheme: str | None = None,
    use_sitemap: bool = True,
    external_images: bool = True,
    on_progress=None,
) -> MirrorStats:
    """Обходит сайт вширь и складывает страницы и картинки в `dest_dir`.

    Обход ограничен со всех сторон — числом страниц, глубиной, объёмом и общим
    временем. Без общего дедлайна любой сайт с календарём или бесконечной
    пагинацией держал бы выгрузку до посинения: в этом проекте на такие грабли
    уже наступали на скане, и правило «у фазы есть бюджет» здесь то же самое.

    `assets_share` — доля времени, удержанная под картинки. Фазы идут по
    очереди, и без этой доли страницы забирают весь бюджет: выгрузка выглядит
    успешной, а фотографий в ней нет, и выясняется это уже при разборе.

    `scheme` фиксирует протокол принудительно; по умолчанию он определяется
    сам — https с откатом на http.
    """
    domain = domain.strip().lower().removeprefix("http://").removeprefix("https://")
    domain = domain.split("/")[0].strip(".")
    host = domain.split(":")[0]

    dest_dir.mkdir(parents=True, exist_ok=True)
    stats = MirrorStats()
    polite = Politeness(respect_robots=respect_robots, per_host_delay=per_host_delay)
    # Картинки с чужого хоста качаем чаще, чем страницы сайта. Пауза в 0,7 с
    # придумана для самописного сайта на слабом хостинге, а на той стороне
    # обычно CDN конструктора: у mebel-ryazane.ru все 23 тысячи адресов ведут
    # на media.lpgenerator.ru, и по 0,7 с выгрузка не уложилась бы в бюджет.
    polite_cdn = Politeness(respect_robots=respect_robots,
                            per_host_delay=min(per_host_delay, 0.25))
    session = requests.Session()
    # Бюджет делится на две части. Страницы качаются первыми и без границы
    # съели бы всё время: 500 страниц по 0,7 секунды это 350 секунд, и на
    # papinalavka.ru картинкам осталась одна минута из семи — приехало 76
    # файлов из 850. Поэтому у страниц свой дедлайн, а доля времени под
    # картинки удержана заранее и сгорает только вместе с ними.
    started_at = time.monotonic()
    deadline = started_at + time_budget
    pages_deadline = started_at + time_budget * (1 - assets_share)
    root = f"{scheme}://{domain}/" if scheme else _pick_root(domain, session, timeout)

    queue: deque[tuple[str, int]] = deque([(root, 0)])
    seen: set[str] = {root}

    # Карта сайта — до обхода: в меню попадает не всё, а страницы из карты
    # надо взять раньше, чем упрёмся в потолок по числу страниц.
    if use_sitemap:
        try:
            for url in _sitemap_urls(root, session, timeout, max_pages):
                url = url.split("#")[0]
                if (_same_site(url, host) and url not in seen
                        and not SKIP_PATH.search(urlparse(url).path)
                        and _ext(urlparse(url).path) not in SKIP_EXT | ASSET_EXT):
                    seen.add(url)
                    queue.append((url, 0))
        except Exception as exc:  # noqa: BLE001
            # Карта — приятное дополнение, а не условие работы: кривой XML
            # или редирект в никуда не должны ронять всю выгрузку.
            log.warning("Карта сайта не разобрана: %s", exc)
    assets: list[str] = []
    site_encoding: str | None = None      # определяется на первой же странице

    # Место на диске спрашиваем не на каждом файле: syscall дешёвый, но
    # картинок тысячи, а свободное место так быстро не меняется.
    disk_checked = [0.0]

    def disk_ok() -> bool:
        if not min_free_bytes:
            return True
        now = time.monotonic()
        if now - disk_checked[0] < 2.0:
            return True
        disk_checked[0] = now
        return shutil.disk_usage(dest_dir).free > min_free_bytes

    def budget_left(until: float) -> bool:
        if stats.bytes >= max_total_bytes:
            stats.stopped_by = stats.stopped_by or "bytes"
            return False
        if not disk_ok():
            stats.stopped_by = stats.stopped_by or "disk"
            return False
        return time.monotonic() < until

    def save(rel: str, data: bytes) -> None:
        path = dest_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        stats.bytes += len(data)

    def note_asset(url: str, *, image: bool = False) -> None:
        """Положить адрес файла в очередь либо записать, почему не положили.

        Отказы считаем именно для картинок: ноль файлов в готовой выгрузке —
        это ноль портфолио, и разбираться, куда они делись, приходится уже
        после разговора с клиентом. Две живые причины — картинки лежат на
        поддомене или CDN (для нас это чужой хост) и картинку отдаёт скрипт,
        у которого в адресе нет расширения.
        """
        if image:
            stats.asset_refs += 1

        def why(reason: str) -> None:
            stats.asset_skipped[reason] = stats.asset_skipped.get(reason, 0) + 1

        ext = _ext(urlparse(url).path)
        if not _same_site(url, host):
            # Сайт на конструкторе держит все фотографии на его CDN — для
            # обхода это чужой хост, а для клиента его собственное портфолио.
            # Поэтому картинки с чужих хостов забираем (стили и скрипты нет:
            # чужое оформление в разборе не нужно и раздувает архив).
            if external_images and ext in IMAGE_EXT:
                if url not in seen:
                    seen.add(url)
                    assets.append(url)
                return
            if image or ext in ASSET_EXT:
                why(f"чужой хост {urlparse(url).netloc.lower()}")
            return
        if ext in SKIP_EXT:
            stats.skipped += 1
            return
        if ext not in ASSET_EXT:
            if image:
                why("адрес без расширения — картинку отдаёт скрипт")
            return
        if url not in seen:
            seen.add(url)
            assets.append(url)

    # --- фазы: сначала страницы, потом картинки ------------------------- #
    def crawl_pages(until: float) -> None:
        nonlocal site_encoding
        while queue and stats.pages < max_pages and budget_left(until):
            url, depth = queue.popleft()
            if SKIP_PATH.search(urlparse(url).path):
                stats.skipped += 1
                continue
            if not polite.allowed(url):
                stats.skipped += 1
                continue
            polite.wait(url)
            try:
                got = _get(url, timeout=timeout, max_bytes=max_file_bytes, session=session)
            except requests.RequestException as exc:
                stats.errors.append(f"{url}: {type(exc).__name__}")
                # Прогресс сообщаем и на неудаче: иначе выгрузка сайта, который
                # отвечает одними отказами, выглядит как зависшая — «страниц 0,
                # файлов 0» и ни строчки движения. Так и было на rgz61.ru.
                if on_progress:
                    on_progress(stats)
                continue
            if not got:
                continue
            status, ctype, raw, final_url = got
            stats.statuses[status] = stats.statuses.get(status, 0) + 1
            if status >= 400 or "html" not in ctype:
                stats.skipped += 1
                if on_progress:
                    on_progress(stats)
                continue

            # Перекодируем в UTF-8 сразу: windows-1251 в репозитории читается как
            # мусор, а тексты клиента — то, ради чего выгрузка и делается.
            html, used_enc = _decode_page(raw, ctype, site_encoding)
            if site_encoding is None and used_enc != "utf-8":
                site_encoding = used_enc      # подсказка для коротких внутренних страниц
            rel = _local_path(final_url)
            save(rel, html.encode("utf-8"))
            stats.pages += 1

            soup = BeautifulSoup(html, "lxml")
            title = (soup.title.get_text(strip=True) if soup.title else "") or ""
            h1 = soup.h1.get_text(strip=True) if soup.h1 else ""
            desc = soup.find("meta", attrs={"name": "description"})
            stats.pages_index.append({
                "url": final_url,
                "file": rel,
                "title": title[:200],
                "h1": h1[:200],
                "description": (desc.get("content", "")[:300] if desc else ""),
                "bytes": len(raw),
            })
            if on_progress:
                on_progress(stats)

            for tag, attr in (("a", "href"), ("link", "href"), ("img", "src"), ("script", "src")):
                for el in soup.find_all(tag):
                    val = (el.get(attr) or "").strip()
                    if not val or val.startswith(("mailto:", "tel:", "javascript:", "data:", "#")):
                        continue
                    nxt = urljoin(final_url, val).split("#")[0]
                    if tag != "a":
                        note_asset(nxt, image=(tag == "img"))
                        continue
                    if not _same_site(nxt, host):
                        continue
                    ext = _ext(urlparse(nxt).path)
                    if ext in SKIP_EXT:
                        stats.skipped += 1
                        continue
                    if ext in ASSET_EXT:
                        note_asset(nxt)
                        continue
                    if depth >= max_depth:
                        continue
                    # Ссылки с запросом пропускаем: на Joomla это ленты и
                    # сортировки — тот же контент под другим адресом. Исключение
                    # только для пагинации: за ней лежат карточки, которых больше
                    # нигде нет.
                    q = urlparse(nxt).query
                    if (q and not _keep_query(q)) or nxt in seen:
                        continue
                    seen.add(nxt)
                    queue.append((nxt, depth + 1))

            for val in _image_refs(soup):
                note_asset(urljoin(final_url, val).split("#")[0], image=True)


    queue_assets: deque[str] = deque()

    def fetch_assets(until: float) -> None:
        # Адреса уже отфильтрованы через seen при обходе, повторов здесь нет.
        queue_assets.extend(assets)
        assets.clear()
        while queue_assets and budget_left(until):
            url = queue_assets.popleft()
            svoy = _same_site(url, host)
            vezhlivost = polite if svoy else polite_cdn
            if not vezhlivost.allowed(url):
                stats.skipped += 1
                continue
            vezhlivost.wait(url)
            try:
                got = _get(url, timeout=timeout, max_bytes=max_file_bytes, session=session)
            except requests.RequestException as exc:
                stats.errors.append(f"{url}: {type(exc).__name__}")
                if on_progress:
                    on_progress(stats)
                continue
            if not got:
                continue
            status, ctype, raw, final_url = got
            stats.statuses[status] = stats.statuses.get(status, 0) + 1
            # HTML в очереди файлов — это не картинка, а страница-заглушка
            # («файл не найден», редирект на главную). Сохранять её незачем:
            # в выгрузке она выглядела бы скачанным файлом.
            if status >= 400 or not raw or "html" in ctype:
                stats.skipped += 1
                if on_progress:
                    on_progress(stats)
                continue
            rel = _local_path(final_url)
            if not svoy:
                # Чужие складываем отдельно и с хостом в пути: иначе два CDN
                # с одинаковым `/images/1.jpg` затрут друг друга, а при разборе
                # будет не видно, где своё, а где с конструктора.
                chuzhoy = _BAD_SEG.sub("_", urlparse(final_url).netloc.lower())
                rel = f"_vneshnie/{chuzhoy}/{rel}"
                stats.assets_external += 1
            save(rel, raw)
            stats.assets += 1
            if on_progress:
                on_progress(stats)

            # Фоновые картинки живут в CSS, а не в разметке — на старых сайтах
            # так подключена добрая половина оформления (у projekt-doma.ru,
            # например, все слайды главной).
            if rel.endswith(".css"):
                css = raw.decode("utf-8", errors="replace")
                for m in _CSS_URL.finditer(css):
                    nxt = urljoin(final_url, m.group(1).strip()).split("#")[0]
                    if (_same_site(nxt, host) and nxt not in seen
                            and _ext(urlparse(nxt).path) in ASSET_EXT):
                        seen.add(nxt)
                        queue_assets.append(nxt)


    # Страницы качаются первыми, картинки — вторыми, и у страниц свой
    # дедлайн: без него они забирают весь бюджет, а картинок в выгрузке
    # не оказывается вовсе. Если же картинки кончились раньше времени,
    # остаток возвращается страницам — и так по кругу, пока есть что
    # качать и на что. Иначе удержанная доля просто сгорала бы на сайте
    # без картинок.
    crawl_pages(pages_deadline)
    fetch_assets(deadline)
    # Условие проверяет не «очередь не пуста», а «есть что качать»: при
    # упёртом потолке страниц crawl_pages возвращается сразу, и очередь,
    # которая уже не убывает, крутила бы этот цикл до самого дедлайна.
    while budget_left(deadline) and (assets or (queue and stats.pages < max_pages)):
        crawl_pages(deadline)
        fetch_assets(deadline)

    if queue:
        stats.pages_left = len(queue)
        stats.stopped_by = stats.stopped_by or (
            "limit" if stats.pages >= max_pages else "deadline")
    if queue_assets or assets:
        stats.assets_left = len(queue_assets) + len(assets)
        stats.stopped_by = stats.stopped_by or "deadline"
    stats.stopped_by = stats.stopped_by or "done"
    (dest_dir / "manifest.json").write_text(
        json.dumps({
            "domain": domain,
            "collected": time.strftime("%Y-%m-%d %H:%M"),
            "pages": stats.pages,
            "assets": stats.assets,
            "stopped_by": stats.stopped_by,
            "pages_left": stats.pages_left,
            "assets_left": stats.assets_left,
            "asset_refs": stats.asset_refs,
            "asset_skipped": stats.asset_skipped,
            "assets_external": stats.assets_external,
            "index": stats.pages_index,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("Выгрузка %s: страниц %d, файлов %d, %.1f МБ, ответы %s (%s);"
             " не добрано страниц %d, файлов %d",
             domain, stats.pages, stats.assets, stats.bytes / 1048576,
             stats.statuses or "нет", stats.stopped_by,
             stats.pages_left, stats.assets_left)
    return stats


def pack_chastyami(
    src_dir: Path,
    dest_dir: Path,
    base: str,
    chast_bytes: int,
    otdat: "Callable[[Path], bool] | None" = None,
) -> list[tuple[str, int]]:
    """Пакует выгрузку в несколько архивов, отдавая каждый по готовности.

    Ради диска, а не ради удобства. Даже с удалением файлов по ходу упаковки
    пик по месту равен целому архиву, и на томе в 9,8 ГБ (свободно бывает 533
    МБ) сайт с тремя тысячами фотографий не помещается никак. Здесь пик равен
    одной части: часть закрывается, уходит наружу через `otdat` и тут же
    удаляется с тома.

    `otdat` возвращает True, если часть принята — только тогда файл удаляется.
    Без него части остаются на месте, и функция ведёт себя как обычный `pack`,
    разрезанный на куски.

    manifest.json кладётся в первую часть первым: разбор начинается с него, и
    качать ради списка страниц гигабайт картинок незачем.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    fajly = [p for p in sorted(src_dir.rglob("*")) if p.is_file()]
    fajly.sort(key=lambda p: (p.name != "manifest.json", p.as_posix()))

    chasti: list[tuple[str, int]] = []
    nomer = 0
    zf: zipfile.ZipFile | None = None
    put: Path | None = None

    def zakryt() -> None:
        nonlocal zf, put
        if zf is None or put is None:
            return
        zf.close()
        razmer = put.stat().st_size
        chasti.append((put.name, razmer))
        if otdat is not None and otdat(put):
            put.unlink()          # принято — на томе больше не держим
        zf, put = None, None

    for path in fajly:
        if zf is None:
            nomer += 1
            put = dest_dir / f"{base}-{nomer:02d}.zip"
            zf = zipfile.ZipFile(put, "w", zipfile.ZIP_DEFLATED, compresslevel=6)
        zf.write(path, path.relative_to(src_dir).as_posix())
        path.unlink()
        # Размер узнаём только у закрытого архива: пока zip открыт, часть
        # данных лежит в буфере и st_size врёт в меньшую сторону. Поэтому
        # граница проверяется по сумме записанного, а не по файлу на диске.
        if sum(i.compress_size for i in zf.infolist()) >= chast_bytes:
            zakryt()
    zakryt()

    for path in sorted(src_dir.rglob("*"), reverse=True):
        path.rmdir() if path.is_dir() else path.unlink()
    src_dir.rmdir()
    return chasti


def pack(src_dir: Path, archive: Path) -> int:
    """Складывает выгрузку в zip, удаляя файлы по мере упаковки.

    Держать на томе обе копии незачем: архив всё равно скачивают целиком, а
    место на диске сервера не бесконечное. Раньше файлы удалялись после
    упаковки — и в пике на диске лежали обе копии сразу: выгрузке на 212 МБ
    требовалось 424 МБ свободных, а на сервере их было 537 на всё про всё.
    Теперь файл удаляется сразу после того, как попал в архив, и пик равен
    одной копии: jpeg не сжимается, так что сумма «архив + ещё не упакованное»
    держится около итогового размера.

    Расплата за это честная: если упаковка оборвётся, распакованного уже не
    останется. Но оно и так удалялось следующей же строкой, а прерванная
    выгрузка в любом случае начинается заново.
    """
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(src_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(src_dir).as_posix())
                path.unlink()
    for path in sorted(src_dir.rglob("*"), reverse=True):
        path.rmdir() if path.is_dir() else path.unlink()
    src_dir.rmdir()
    return archive.stat().st_size
