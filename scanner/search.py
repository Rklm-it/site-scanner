"""Поставщики поисковой выдачи.

По умолчанию используется DuckDuckGo (HTML-эндпоинт, без ключа).
Опционально — Google Custom Search и SerpAPI, если заданы ключи в env.
"""

from __future__ import annotations

import os
import time
from urllib.parse import parse_qs, unquote, urlparse

import requests
from bs4 import BeautifulSoup

from .fetcher import DEFAULT_HEADERS

DDG_HTML = "https://html.duckduckgo.com/html/"
GOOGLE_CSE = "https://www.googleapis.com/customsearch/v1"
SERPAPI = "https://serpapi.com/search"


def _unwrap_ddg(href: str) -> str | None:
    """DuckDuckGo оборачивает ссылки в редирект /l/?uddg=... — раскручиваем."""
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        uddg = parse_qs(parsed.query).get("uddg")
        if uddg:
            return unquote(uddg[0])
        return None
    if parsed.scheme in ("http", "https"):
        return href
    return None


def search_duckduckgo(query: str, *, max_results: int = 20, pause: float = 1.5) -> list[str]:
    urls: list[str] = []
    session = requests.Session()
    for page in range(0, max_results, 25):
        try:
            resp = session.post(
                DDG_HTML,
                data={"q": query, "s": str(page)},
                headers=DEFAULT_HEADERS,
                timeout=15,
            )
            resp.raise_for_status()
        except requests.RequestException:
            break
        soup = BeautifulSoup(resp.text, "lxml")
        anchors = soup.select("a.result__a")
        if not anchors:
            break
        for a in anchors:
            target = _unwrap_ddg(a.get("href", ""))
            if target:
                urls.append(target)
        if len(urls) >= max_results:
            break
        time.sleep(pause)
    return urls[:max_results]


def search_google_cse(query: str, *, max_results: int = 20) -> list[str]:
    key = os.environ.get("GOOGLE_API_KEY")
    cx = os.environ.get("GOOGLE_CSE_CX")
    if not (key and cx):
        return []
    urls: list[str] = []
    for start in range(1, min(max_results, 100), 10):
        try:
            resp = requests.get(
                GOOGLE_CSE,
                params={"key": key, "cx": cx, "q": query, "start": start, "num": 10},
                timeout=15,
            )
            resp.raise_for_status()
        except requests.RequestException:
            break
        items = resp.json().get("items", [])
        if not items:
            break
        urls += [it["link"] for it in items if it.get("link")]
        if len(urls) >= max_results:
            break
    return urls[:max_results]


def search_serpapi(query: str, *, max_results: int = 20) -> list[str]:
    key = os.environ.get("SERPAPI_KEY")
    if not key:
        return []
    try:
        resp = requests.get(
            SERPAPI,
            params={"q": query, "api_key": key, "num": max_results, "engine": "google"},
            timeout=20,
        )
        resp.raise_for_status()
    except requests.RequestException:
        return []
    organic = resp.json().get("organic_results", [])
    return [r["link"] for r in organic if r.get("link")][:max_results]


PROVIDERS = {
    "duckduckgo": search_duckduckgo,
    "google": search_google_cse,
    "serpapi": search_serpapi,
}


def search(query: str, *, provider: str = "duckduckgo", max_results: int = 20) -> list[str]:
    """Возвращает список URL по одному поисковому запросу."""
    fn = PROVIDERS.get(provider)
    if fn is None:
        raise ValueError(f"Неизвестный провайдер поиска: {provider}")
    return fn(query, max_results=max_results)
