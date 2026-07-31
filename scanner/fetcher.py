"""HTTP-загрузка страниц: детект кодировки, обработка битого SSL, повторы."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

import requests

try:  # charset-normalizer идёт в зависимостях requests
    from charset_normalizer import from_bytes as _cn_from_bytes
except Exception:  # pragma: no cover
    _cn_from_bytes = None

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 site-scanner/0.2"
)

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru,en;q=0.8",
}

_CHARSET_HDR = re.compile(r"charset=[\"']?([\w\-]+)", re.I)
_META_CHARSET = re.compile(rb"""<meta[^>]+charset=["']?([\w\-]+)""", re.I)


@dataclass
class FetchResult:
    url: str
    final_url: str | None = None
    status: int | None = None
    headers: dict[str, str] | None = None
    html: str = ""
    load_ms: int | None = None
    https: bool = False
    tls_error: bool = False
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.status is not None and self.status < 400


def _normalize(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def detect_encoding(raw: bytes, headers: dict[str, str]) -> str:
    """Определяет кодировку: заголовок → <meta charset> → авто-детект.

    Критично для рунета: старые сайты нередко отдают windows-1251 без
    корректного HTTP-заголовка, и без этого текст читается как мусор.
    """
    ctype = headers.get("content-type", "")
    m = _CHARSET_HDR.search(ctype)
    if m:
        return m.group(1)

    m2 = _META_CHARSET.search(raw[:4096])
    if m2:
        try:
            return m2.group(1).decode("ascii")
        except UnicodeDecodeError:
            pass

    if _cn_from_bytes is not None:
        best = _cn_from_bytes(raw[:200_000]).best()
        if best and best.encoding:
            return best.encoding

    return "utf-8"


def _decode(raw: bytes, headers: dict[str, str]) -> str:
    enc = detect_encoding(raw, headers)
    try:
        return raw.decode(enc, errors="replace")
    except (LookupError, TypeError):
        return raw.decode("utf-8", errors="replace")


def fetch(
    url: str,
    *,
    timeout: float = 12.0,
    max_bytes: int = 3_000_000,
    session: requests.Session | None = None,
    max_total: float | None = None,
) -> FetchResult:
    """Скачивает HTML страницы.

    Пробует https, при ошибке TLS/соединения — http, и фиксирует факт
    битого сертификата (``tls_error``) — это отдельный сигнал заброшенности.

    ``timeout`` у requests — потолок на ОДНУ операцию с сокетом, а не на запрос
    целиком: цепочка редиректов (их до 30) множит его на каждый переход, плюс
    сверху ложится вторая попытка по http. Поэтому весь вызов ограничен ещё и
    ``max_total`` (по умолчанию — 2.5 таймаута): именно такие сайты и держали
    скан на одном «пункте».
    """
    sess = session or requests.Session()
    target = _normalize(url)
    candidates = [target]
    if target.startswith("https://"):
        candidates.append("http://" + target[len("https://"):])

    last_error: str | None = None
    tls_error = False
    hard_deadline = time.perf_counter() + (max_total if max_total is not None else timeout * 2.5)

    for candidate in candidates:
        started = time.perf_counter()
        left = hard_deadline - started
        if left <= 0:
            last_error = last_error or f"превышен общий лимит {timeout * 2.5:.0f}с на загрузку"
            break
        try:
            resp = sess.get(
                candidate,
                headers=DEFAULT_HEADERS,
                timeout=min(timeout, left),
                allow_redirects=True,
                stream=True,
            )
            # Жёсткий дедлайн на чтение тела: при stream=True таймаут requests
            # не покрывает медленную «струйку» байт, и read() может висеть
            # намного дольше timeout. Читаем чанками с общим лимитом по времени.
            deadline = min(started + timeout, hard_deadline)
            buf = bytearray()
            try:
                for chunk in resp.iter_content(16384):
                    if chunk:
                        buf += chunk
                    if len(buf) >= max_bytes or time.perf_counter() > deadline:
                        break
            finally:
                resp.close()
            raw = bytes(buf[:max_bytes])
            elapsed = int((time.perf_counter() - started) * 1000)
            headers = {k.lower(): v for k, v in resp.headers.items()}

            return FetchResult(
                url=url,
                final_url=resp.url,
                status=resp.status_code,
                headers=headers,
                html=_decode(raw, headers),
                load_ms=elapsed,
                https=resp.url.startswith("https://"),
                tls_error=tls_error,
            )
        except requests.exceptions.SSLError as exc:
            tls_error = True
            last_error = f"SSLError: {exc}"
            continue
        except requests.RequestException as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            continue

    return FetchResult(url=url, error=last_error or "unknown fetch error", tls_error=tls_error)
