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
import time
import zipfile
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlparse

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
ASSET_EXT = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".bmp",
    ".css", ".js",
}
# Служебные ветки CMS: там нет содержимого, ради которого затевается разбор,
# зато обход в них уходит охотно и тратит бюджет.
SKIP_PATH = re.compile(
    r"/(administrator|wp-admin|wp-login|bitrix|admin|login|logout|cart|basket"
    r"|korzina|search|component/(search|users)|index\.php/component)",
    re.I,
)
_CSS_URL = re.compile(r"""url\(\s*['"]?([^'")]+)['"]?\s*\)""", re.I)
_BAD_SEG = re.compile(r"[^\w.\-]+", re.U)
_CHARSET_HDR = re.compile(r"charset=[\"']?([\w\-]+)", re.I)
_META_CHARSET = re.compile(rb"""charset=["']?([\w\-]+)""", re.I)


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
    errors: list[str] = field(default_factory=list)
    pages_index: list[dict] = field(default_factory=list)
    archive: str | None = None
    stopped_by: str | None = None      # limit / deadline / done


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


def _local_path(url: str) -> str:
    """Адрес → путь внутри архива.

    Запрос (`?...`) в имя не попадает: на Joomla по нему живут ленты и
    сортировки, то есть тот же контент под другим адресом. Точки-сегменты
    вырезаются, иначе `..` в чужой ссылке увёл бы запись выше папки выгрузки.
    """
    parsed = urlparse(url)
    raw = [s for s in parsed.path.split("/") if s not in ("", ".", "..")]
    segments = [_BAD_SEG.sub("_", s)[:120] or "_" for s in raw]
    if not segments:
        return "index.html"
    if _ext(segments[-1]) in ASSET_EXT:
        return "/".join(segments)
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


def _pick_root(domain: str, session: requests.Session, timeout: float) -> str:
    """Выбирает рабочую схему для стартовой страницы.

    Сначала https, при неудаче — http. Это не перестраховка: у одного из лидов
    (`print-rf.ru`) сертификат выписан на чужое имя, и https не открывается
    вообще — с жёстко зашитым https выгрузка такого сайта вернула бы ноль
    страниц, а причина была бы неочевидна.
    """
    for scheme in ("https", "http"):
        url = f"{scheme}://{domain}/"
        try:
            resp = session.head(url, headers=DEFAULT_HEADERS, timeout=timeout,
                                allow_redirects=True)
            if resp.status_code < 400:
                return resp.url
        except requests.RequestException:
            continue
        # HEAD поддерживают не все старые сайты — пробуем обычным запросом
        try:
            resp = session.get(url, headers=DEFAULT_HEADERS, timeout=timeout,
                               allow_redirects=True, stream=True)
            resp.close()
            if resp.status_code < 400:
                return resp.url
        except requests.RequestException:
            continue
    return f"https://{domain}/"


def run(
    domain: str,
    dest_dir: Path,
    *,
    max_pages: int = 150,
    max_depth: int = 3,
    time_budget: float = 420.0,
    per_host_delay: float = 0.7,
    respect_robots: bool = True,
    max_total_bytes: int = 80 * 1024 * 1024,
    max_file_bytes: int = 15 * 1024 * 1024,
    timeout: float = 15.0,
    scheme: str | None = None,
    on_progress=None,
) -> MirrorStats:
    """Обходит сайт вширь и складывает страницы и картинки в `dest_dir`.

    Обход ограничен со всех сторон — числом страниц, глубиной, объёмом и общим
    временем. Без общего дедлайна любой сайт с календарём или бесконечной
    пагинацией держал бы выгрузку до посинения: в этом проекте на такие грабли
    уже наступали на скане, и правило «у фазы есть бюджет» здесь то же самое.

    `scheme` фиксирует протокол принудительно; по умолчанию он определяется
    сам — https с откатом на http.
    """
    domain = domain.strip().lower().removeprefix("http://").removeprefix("https://")
    domain = domain.split("/")[0].strip(".")
    host = domain.split(":")[0]

    dest_dir.mkdir(parents=True, exist_ok=True)
    stats = MirrorStats()
    polite = Politeness(respect_robots=respect_robots, per_host_delay=per_host_delay)
    session = requests.Session()
    deadline = time.monotonic() + time_budget
    root = f"{scheme}://{domain}/" if scheme else _pick_root(domain, session, timeout)

    queue: deque[tuple[str, int]] = deque([(root, 0)])
    seen: set[str] = {root}
    assets: list[str] = []
    site_encoding: str | None = None      # определяется на первой же странице

    def budget_left() -> bool:
        if time.monotonic() > deadline:
            stats.stopped_by = stats.stopped_by or "deadline"
            return False
        if stats.bytes >= max_total_bytes:
            stats.stopped_by = stats.stopped_by or "limit"
            return False
        return True

    def save(rel: str, data: bytes) -> None:
        path = dest_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        stats.bytes += len(data)

    # --- страницы -------------------------------------------------------- #
    while queue and stats.pages < max_pages and budget_left():
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
            continue
        if not got:
            continue
        status, ctype, raw, final_url = got
        if status >= 400 or "html" not in ctype:
            stats.skipped += 1
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
                if not _same_site(nxt, host):
                    continue
                ext = _ext(urlparse(nxt).path)
                if ext in SKIP_EXT:
                    stats.skipped += 1
                    continue
                if ext in ASSET_EXT:
                    if nxt not in seen:
                        seen.add(nxt)
                        assets.append(nxt)
                    continue
                if tag != "a" or depth >= max_depth:
                    continue
                # Ссылки с запросом пропускаем: на Joomla это ленты и
                # сортировки — тот же контент под другим адресом.
                if urlparse(nxt).query or nxt in seen:
                    continue
                seen.add(nxt)
                queue.append((nxt, depth + 1))

    if queue and stats.pages >= max_pages:
        stats.stopped_by = stats.stopped_by or "limit"

    # --- картинки, стили, скрипты ---------------------------------------- #
    # Отдельным проходом после страниц: если бюджет кончится, лучше остаться с
    # полным набором текстов и без части картинок, чем наоборот.
    queue_assets = deque(assets)
    while queue_assets and budget_left():
        url = queue_assets.popleft()
        if not polite.allowed(url):
            stats.skipped += 1
            continue
        polite.wait(url)
        try:
            got = _get(url, timeout=timeout, max_bytes=max_file_bytes, session=session)
        except requests.RequestException as exc:
            stats.errors.append(f"{url}: {type(exc).__name__}")
            continue
        if not got:
            continue
        status, ctype, raw, final_url = got
        if status >= 400 or not raw:
            stats.skipped += 1
            continue
        rel = _local_path(final_url)
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

    stats.stopped_by = stats.stopped_by or "done"
    (dest_dir / "manifest.json").write_text(
        json.dumps({
            "domain": domain,
            "collected": time.strftime("%Y-%m-%d %H:%M"),
            "pages": stats.pages,
            "assets": stats.assets,
            "stopped_by": stats.stopped_by,
            "index": stats.pages_index,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("Выгрузка %s: страниц %d, файлов %d, %.1f МБ (%s)",
             domain, stats.pages, stats.assets, stats.bytes / 1048576, stats.stopped_by)
    return stats


def pack(src_dir: Path, archive: Path) -> int:
    """Складывает выгрузку в zip и удаляет распакованное.

    Держать на томе обе копии незачем: архив всё равно скачивают целиком, а
    место на диске сервера не бесконечное.
    """
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(src_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(src_dir).as_posix())
    for path in sorted(src_dir.rglob("*"), reverse=True):
        path.rmdir() if path.is_dir() else path.unlink()
    src_dir.rmdir()
    return archive.stat().st_size
