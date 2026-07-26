"""Поставщики поисковой выдачи: Яндекс и Google (+ опционально SerpAPI, DDG).

Прямой скрапинг выдачи Яндекса и Google нежизнеспособен — оба быстро
отдают капчу и банят по IP. Поэтому используем официальные API:

* Google  — Custom Search JSON API (ключ ``GOOGLE_API_KEY`` + ``GOOGLE_CSE_CX``)
* Яндекс  — Search API / XML (``YANDEX_API_KEY`` + ``YANDEX_FOLDER_ID``
            либо классические ``YANDEX_XML_USER`` + ``YANDEX_XML_KEY``)
* SerpAPI — турнкей-обёртка над обоими движками (``SERPAPI_KEY``)
* DuckDuckGo — бесключевой запасной вариант (нестабилен, лимитируется)

Ключи задаются переменными окружения (можно через файл .env / export).
"""

from __future__ import annotations

import os
import sys
import time
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, unquote, urlparse

import requests
from bs4 import BeautifulSoup

from .fetcher import DEFAULT_HEADERS

GOOGLE_CSE = "https://www.googleapis.com/customsearch/v1"
YANDEX_XML = "https://yandex.ru/search/xml"
SERPAPI = "https://serpapi.com/search"
DDG_HTML = "https://html.duckduckgo.com/html/"

_warned: set[str] = set()


def _warn_once(key: str, message: str) -> None:
    if key not in _warned:
        _warned.add(key)
        print(f"[search] {message}", file=sys.stderr)


# --------------------------------------------------------------------------- #
# Google Custom Search JSON API
# --------------------------------------------------------------------------- #
def search_google_cse(query: str, *, max_results: int = 20) -> list[str]:
    key = os.environ.get("GOOGLE_API_KEY")
    cx = os.environ.get("GOOGLE_CSE_CX")
    if not (key and cx):
        _warn_once(
            "google",
            "провайдер google пропущен: задайте GOOGLE_API_KEY и GOOGLE_CSE_CX "
            "(https://developers.google.com/custom-search/v1/overview)",
        )
        return []

    urls: list[str] = []
    for start in range(1, min(max_results, 100) + 1, 10):
        try:
            resp = requests.get(
                GOOGLE_CSE,
                params={"key": key, "cx": cx, "q": query, "start": start, "num": 10, "hl": "ru"},
                timeout=15,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            _warn_once("google_err", f"ошибка Google CSE: {exc}")
            break
        items = resp.json().get("items", [])
        if not items:
            break
        urls += [it["link"] for it in items if it.get("link")]
        if len(urls) >= max_results:
            break
    return urls[:max_results]


# --------------------------------------------------------------------------- #
# Яндекс XML / Search API
# --------------------------------------------------------------------------- #
def _yandex_auth() -> dict[str, str] | None:
    apikey = os.environ.get("YANDEX_API_KEY")
    folderid = os.environ.get("YANDEX_FOLDER_ID")
    if apikey and folderid:
        return {"apikey": apikey, "folderid": folderid}
    user = os.environ.get("YANDEX_XML_USER")
    key = os.environ.get("YANDEX_XML_KEY")
    if user and key:
        return {"user": user, "key": key}
    return None


def search_yandex_xml(query: str, *, max_results: int = 20) -> list[str]:
    auth = _yandex_auth()
    if auth is None:
        _warn_once(
            "yandex",
            "провайдер yandex пропущен: задайте YANDEX_API_KEY + YANDEX_FOLDER_ID "
            "(Yandex Cloud Search API) либо YANDEX_XML_USER + YANDEX_XML_KEY "
            "(https://yandex.ru/dev/xml/)",
        )
        return []

    per_page = min(max_results, 100)
    groupby = f'attr="".mode=flat.groups-on-page={per_page}.docs-in-group=1'
    urls: list[str] = []

    for page in range(0, 11):  # Яндекс отдаёт не больше ~1000 результатов
        params = {**auth, "query": query, "l10n": "ru", "groupby": groupby, "page": page}
        try:
            resp = requests.get(YANDEX_XML, params=params, headers=DEFAULT_HEADERS, timeout=20)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
        except (requests.RequestException, ET.ParseError) as exc:
            _warn_once("yandex_err", f"ошибка Yandex XML: {exc}")
            break

        error = root.find(".//response/error")
        if error is not None:
            _warn_once("yandex_api_err", f"Yandex XML вернул ошибку: {error.text}")
            break

        found = [el.text for el in root.findall(".//doc/url") if el.text]
        if not found:
            break
        urls += found
        if len(urls) >= max_results:
            break

    return urls[:max_results]


# --------------------------------------------------------------------------- #
# SerpAPI — обёртка над Google и Яндексом
# --------------------------------------------------------------------------- #
def _serpapi(query: str, engine: str, max_results: int) -> list[str]:
    key = os.environ.get("SERPAPI_KEY")
    if not key:
        _warn_once("serpapi", "провайдер serpapi* пропущен: задайте SERPAPI_KEY")
        return []
    params = {"q": query, "api_key": key, "num": max_results, "engine": engine, "hl": "ru"}
    if engine == "yandex":
        params.update({"text": query, "yandex_domain": "yandex.ru"})
    try:
        resp = requests.get(SERPAPI, params=params, timeout=25)
        resp.raise_for_status()
    except requests.RequestException as exc:
        _warn_once("serpapi_err", f"ошибка SerpAPI ({engine}): {exc}")
        return []
    organic = resp.json().get("organic_results", [])
    return [r["link"] for r in organic if r.get("link")][:max_results]


def search_serpapi_google(query: str, *, max_results: int = 20) -> list[str]:
    return _serpapi(query, "google", max_results)


def search_serpapi_yandex(query: str, *, max_results: int = 20) -> list[str]:
    return _serpapi(query, "yandex", max_results)


# --------------------------------------------------------------------------- #
# DuckDuckGo — бесключевой запасной вариант
# --------------------------------------------------------------------------- #
def _unwrap_ddg(href: str) -> str | None:
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        uddg = parse_qs(parsed.query).get("uddg")
        return unquote(uddg[0]) if uddg else None
    return href if parsed.scheme in ("http", "https") else None


def search_duckduckgo(query: str, *, max_results: int = 20, pause: float = 1.5) -> list[str]:
    urls: list[str] = []
    session = requests.Session()
    for page in range(0, max_results, 25):
        try:
            resp = session.post(
                DDG_HTML, data={"q": query, "s": str(page)}, headers=DEFAULT_HEADERS, timeout=15
            )
            resp.raise_for_status()
        except requests.RequestException:
            break
        anchors = BeautifulSoup(resp.text, "lxml").select("a.result__a")
        if not anchors:
            break
        urls += [t for a in anchors if (t := _unwrap_ddg(a.get("href", "")))]
        if len(urls) >= max_results:
            break
        time.sleep(pause)
    return urls[:max_results]


# --------------------------------------------------------------------------- #
# Реестр провайдеров и точки входа
# --------------------------------------------------------------------------- #
PROVIDERS = {
    "yandex": search_yandex_xml,
    "google": search_google_cse,
    "serpapi_google": search_serpapi_google,
    "serpapi_yandex": search_serpapi_yandex,
    "duckduckgo": search_duckduckgo,
}

DEFAULT_PROVIDERS = ["yandex", "google"]


def search(query: str, *, provider: str = "yandex", max_results: int = 20) -> list[str]:
    """URL по одному запросу через один провайдер."""
    fn = PROVIDERS.get(provider)
    if fn is None:
        raise ValueError(f"Неизвестный провайдер поиска: {provider}")
    return fn(query, max_results=max_results)


def search_many(query: str, *, providers: list[str], max_results: int = 20) -> list[str]:
    """URL по одному запросу через несколько провайдеров с объединением.

    Результаты чередуются по провайдерам (round-robin), чтобы верхние
    позиции разных движков попадали в начало списка, а дубли убираются.
    """
    per_provider = [search(query, provider=p, max_results=max_results) for p in providers]
    merged: list[str] = []
    seen: set[str] = set()
    for i in range(max(len(lst) for lst in per_provider) if per_provider else 0):
        for lst in per_provider:
            if i < len(lst) and lst[i] not in seen:
                seen.add(lst[i])
                merged.append(lst[i])
    return merged
