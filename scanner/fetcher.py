"""HTTP-загрузка страниц с таймаутами и мягкими повторами."""

from __future__ import annotations

import time
from dataclasses import dataclass

import requests

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 site-scanner/0.1"
)

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru,en;q=0.8",
}


@dataclass
class FetchResult:
    url: str
    final_url: str | None = None
    status: int | None = None
    headers: dict[str, str] | None = None
    html: str = ""
    load_ms: int | None = None
    https: bool = False
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.status is not None and self.status < 400


def _normalize(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def fetch(
    url: str,
    *,
    timeout: float = 12.0,
    max_bytes: int = 3_000_000,
    session: requests.Session | None = None,
) -> FetchResult:
    """Скачивает HTML страницы.

    Пробует https, при неудаче — http. Возвращает FetchResult с сырым
    HTML (обрезанным до ``max_bytes``) и метаданными ответа.
    """
    sess = session or requests.Session()
    target = _normalize(url)
    candidates = [target]
    if target.startswith("https://"):
        candidates.append("http://" + target[len("https://"):])

    last_error: str | None = None
    for candidate in candidates:
        started = time.perf_counter()
        try:
            resp = sess.get(
                candidate,
                headers=DEFAULT_HEADERS,
                timeout=timeout,
                allow_redirects=True,
                stream=True,
            )
            content = resp.raw.read(max_bytes, decode_content=True) or b""
            resp.close()
            elapsed = int((time.perf_counter() - started) * 1000)

            encoding = resp.encoding or resp.apparent_encoding or "utf-8"
            try:
                html = content.decode(encoding, errors="replace")
            except (LookupError, TypeError):
                html = content.decode("utf-8", errors="replace")

            return FetchResult(
                url=url,
                final_url=resp.url,
                status=resp.status_code,
                headers={k.lower(): v for k, v in resp.headers.items()},
                html=html,
                load_ms=elapsed,
                https=resp.url.startswith("https://"),
            )
        except requests.RequestException as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            continue

    return FetchResult(url=url, error=last_error or "unknown fetch error")
