"""Поставщики поисковой выдачи: Яндекс и Google (+ опционально SerpAPI, DDG).

Прямой скрапинг выдачи Яндекса и Google нежизнеспособен — оба быстро
отдают капчу и банят по IP. Поэтому используем официальные API:

* Google  — Custom Search JSON API (ключ ``GOOGLE_API_KEY`` + ``GOOGLE_CSE_CX``)
* Яндекс  — Cloud Search API v2 (``YANDEX_API_KEY`` + ``YANDEX_FOLDER_ID``)
            либо классический XML (``YANDEX_XML_USER`` + ``YANDEX_XML_KEY``)
* SerpAPI — турнкей-обёртка над обоими движками (``SERPAPI_KEY``)
* DuckDuckGo — бесключевой запасной вариант (нестабилен, лимитируется)

Ключи задаются переменными окружения (можно через файл .env / export).
"""

from __future__ import annotations

import base64
import logging
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
YANDEX_CLOUD_ASYNC = "https://searchapi.api.cloud.yandex.net/v2/web/searchAsync"
YANDEX_OPERATION = "https://operation.api.cloud.yandex.net/operations/"
SERPAPI = "https://serpapi.com/search"
DDG_HTML = "https://html.duckduckgo.com/html/"

log = logging.getLogger("scanner.search")

_warned: set[str] = set()

_RETRY_STATUS = {429, 500, 502, 503, 504}


def _warn_once(key: str, message: str) -> None:
    if key not in _warned:
        _warned.add(key)
        print(f"[search] {message}", file=sys.stderr)


def _expired(deadline: float | None) -> bool:
    return deadline is not None and time.monotonic() >= deadline


def _http(method: str, url: str, *, retries: int = 2, backoff: float = 1.5,
          deadline: float | None = None, **kw):
    """HTTP-запрос с повторами на сетевых ошибках и кодах 429/5xx.

    Обращается к ``requests.get``/``requests.post`` по имени, чтобы их можно
    было замокать в тестах.

    ``deadline`` (monotonic) — общий потолок фазы сбора. Без него повторы и
    таймауты перемножались: до 3 попыток по 20-30с на страницу выдачи, и один
    молчащий поисковик держал поток десятками минут уже после того, как фаза
    была брошена по бюджету.
    """
    fn = requests.get if method == "get" else requests.post
    for attempt in range(retries + 1):
        if _expired(deadline):
            raise requests.exceptions.Timeout(f"бюджет сбора выдачи исчерпан: {url}")
        if deadline is not None and isinstance(kw.get("timeout"), (int, float)):
            kw = {**kw, "timeout": max(1.0, min(kw["timeout"], deadline - time.monotonic()))}
        try:
            resp = fn(url, **kw)
        except requests.RequestException:
            if attempt < retries and not _expired(deadline):
                time.sleep(_capped_sleep(backoff ** attempt, deadline))
                continue
            raise
        if getattr(resp, "status_code", 200) in _RETRY_STATUS and attempt < retries \
                and not _expired(deadline):
            time.sleep(_capped_sleep(backoff ** attempt, deadline))
            continue
        return resp


def _capped_sleep(seconds: float, deadline: float | None) -> float:
    """Пауза перед повтором, но не дольше остатка бюджета."""
    if deadline is None:
        return seconds
    return max(0.0, min(seconds, deadline - time.monotonic()))


# --------------------------------------------------------------------------- #
# Google Custom Search JSON API
# --------------------------------------------------------------------------- #
def search_google_cse(query: str, *, max_results: int = 20,
                      deadline: float | None = None) -> list[str]:
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
        if _expired(deadline):
            break
        try:
            resp = _http(
                "get", GOOGLE_CSE,
                params={"key": key, "cx": cx, "q": query, "start": start, "num": 10, "hl": "ru"},
                timeout=15, deadline=deadline,
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
# Яндекс: Cloud Search API v2 (apikey+folder) или классический XML (user+key)
# --------------------------------------------------------------------------- #
def _parse_yandex_xml(raw: bytes) -> tuple[list[str], str | None]:
    """Разбирает ответ Яндекса (yandexsearch XML) → (urls, error)."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        return [], f"не разобрать XML: {exc}"
    error = root.find(".//response/error")
    if error is not None:
        return [], (error.text or "unknown error")
    return [el.text for el in root.findall(".//doc/url") if el.text], None


def _yandex_classic(query: str, auth: dict[str, str], max_results: int,
                    deadline: float | None = None) -> list[str]:
    """GET yandex.ru/search/xml. auth = {user,key} или {apikey,folderid}.
    Этот endpoint принимает и Cloud-ключи (apikey+folderid), и старые user+key."""
    per_page = min(max_results, 100)
    groupby = f'attr="".mode=flat.groups-on-page={per_page}.docs-in-group=1'
    urls: list[str] = []

    for page in range(0, 11):
        if _expired(deadline):
            break
        params = {**auth, "query": query, "l10n": "ru", "groupby": groupby, "page": page}
        try:
            resp = _http("get", YANDEX_XML, params=params, headers=DEFAULT_HEADERS,
                         timeout=20, deadline=deadline)
            resp.raise_for_status()
        except requests.RequestException as exc:
            log.warning("Yandex XML запрос упал: %s", exc)
            break

        found, error = _parse_yandex_xml(resp.content)
        if error:
            log.warning("Yandex XML ошибка API по «%s»: %s", query, error)
            break
        if not found:
            break
        urls += found
        if len(urls) >= max_results:
            break

    return urls[:max_results]


def search_yandex_xml(query: str, *, max_results: int = 20,
                      deadline: float | None = None) -> list[str]:
    """Классический Яндекс.XML по user+key."""
    user = os.environ.get("YANDEX_XML_USER")
    key = os.environ.get("YANDEX_XML_KEY")
    if not (user and key):
        return []
    return _yandex_classic(query, {"user": user, "key": key}, max_results, deadline)


def _yandex_operation_rawdata(data: dict, headers: dict, *, poll_timeout: int = 30,
                              deadline: float | None = None) -> str | None:
    """Достаёт base64 rawData из ответа v2: либо сразу, либо дождавшись
    асинхронной операции (searchAsync возвращает Operation).

    Ждём по часам, а не «30 итераций». Раньше на каждой итерации спали секунду
    и делали запрос с таймаутом 20с и двумя повторами — то есть цикл мог идти
    полчаса вместо заявленных 30 секунд, и это на каждую из 5 страниц выдачи.
    """
    if data.get("rawData"):                      # синхронный ответ
        return data["rawData"]
    op_id = data.get("id")
    if not op_id:
        log.warning("Yandex Cloud: неожиданный ответ без id/rawData: %s", str(data)[:400])
        return None

    until = time.monotonic() + poll_timeout
    if deadline is not None:
        until = min(until, deadline)
    while True:
        if data.get("done"):
            if data.get("error"):
                log.warning("Yandex Cloud operation error: %s", str(data["error"])[:400])
                return None
            return (data.get("response") or {}).get("rawData")
        if time.monotonic() >= until:
            break
        time.sleep(1)
        try:
            r = _http("get", YANDEX_OPERATION + op_id, headers=headers, timeout=20,
                      deadline=until)
        except requests.RequestException as exc:
            log.warning("Yandex Cloud: опрос операции упал: %s", exc)
            return None
        if r.status_code != 200:
            log.warning("Yandex Cloud operation HTTP %s: %s", r.status_code, r.text[:300])
            return None
        data = r.json()
    log.warning("Yandex Cloud: операция не завершилась за %dс", poll_timeout)
    return None


def search_yandex_cloud(query: str, *, max_results: int = 20,
                        deadline: float | None = None) -> list[str]:
    """Yandex Search API v2 (Yandex Cloud). Асинхронный поток:
    POST searchAsync → дождаться операции → base64-XML → тот же парсер."""
    api_key = os.environ.get("YANDEX_API_KEY")
    folder = os.environ.get("YANDEX_FOLDER_ID")
    if not (api_key and folder):
        return []

    headers = {"Authorization": f"Api-Key {api_key}", "Content-Type": "application/json"}
    urls: list[str] = []

    for page in range(0, 5):
        if _expired(deadline):
            break
        body = {
            "query": {"searchType": "SEARCH_TYPE_RU", "queryText": query, "page": str(page)},
            "folderId": folder,
            "responseFormat": "FORMAT_XML",
        }
        try:
            resp = _http("post", YANDEX_CLOUD_ASYNC, json=body, headers=headers, timeout=30,
                         deadline=deadline)
        except requests.RequestException as exc:
            log.warning("Yandex Cloud searchAsync упал: %s", exc)
            break
        if resp.status_code != 200:
            log.warning("Yandex Cloud searchAsync HTTP %s: %s", resp.status_code, resp.text[:400])
            break

        raw_b64 = _yandex_operation_rawdata(resp.json(), headers, deadline=deadline)
        if not raw_b64:
            break

        found, error = _parse_yandex_xml(base64.b64decode(raw_b64))
        if error:
            log.warning("Yandex Cloud ошибка API по «%s»: %s", query, error)
            break
        if not found:
            break
        urls += found
        log.info("Яндекс cloud v2: страница %d, +%d url по «%s»", page, len(found), query)
        if len(urls) >= max_results:
            break

    return urls[:max_results]


def search_yandex(query: str, *, max_results: int = 20,
                  deadline: float | None = None) -> list[str]:
    """Единая точка входа для Яндекса.

    Если заданы Cloud-ключи (apikey+folder) — сначала пробуем классический
    endpoint yandex.ru/search/xml (он их принимает и стабильно отдаёт XML),
    при пустом ответе — новый Cloud Search API v2. Иначе — user+key.
    """
    apikey = os.environ.get("YANDEX_API_KEY")
    folder = os.environ.get("YANDEX_FOLDER_ID")
    if apikey and folder:
        urls = search_yandex_cloud(query, max_results=max_results, deadline=deadline)
        log.info("Яндекс (cloud v2): %d url по «%s»", len(urls), query)
        return urls

    user = os.environ.get("YANDEX_XML_USER")
    key = os.environ.get("YANDEX_XML_KEY")
    if user and key:
        return _yandex_classic(query, {"user": user, "key": key}, max_results, deadline)

    _warn_once(
        "yandex",
        "провайдер yandex пропущен: задайте YANDEX_API_KEY + YANDEX_FOLDER_ID "
        "либо YANDEX_XML_USER + YANDEX_XML_KEY",
    )
    return []


# --------------------------------------------------------------------------- #
# SerpAPI — обёртка над Google и Яндексом
# --------------------------------------------------------------------------- #
def _serpapi(query: str, engine: str, max_results: int,
             deadline: float | None = None) -> list[str]:
    key = os.environ.get("SERPAPI_KEY")
    if not key:
        _warn_once("serpapi", "провайдер serpapi* пропущен: задайте SERPAPI_KEY")
        return []
    params = {"q": query, "api_key": key, "num": max_results, "engine": engine, "hl": "ru"}
    if engine == "yandex":
        params.update({"text": query, "yandex_domain": "yandex.ru"})
    try:
        resp = _http("get", SERPAPI, params=params, timeout=25, deadline=deadline)
        resp.raise_for_status()
    except requests.RequestException as exc:
        _warn_once("serpapi_err", f"ошибка SerpAPI ({engine}): {exc}")
        return []
    organic = resp.json().get("organic_results", [])
    return [r["link"] for r in organic if r.get("link")][:max_results]


def search_serpapi_google(query: str, *, max_results: int = 20,
                          deadline: float | None = None) -> list[str]:
    return _serpapi(query, "google", max_results, deadline)


def search_serpapi_yandex(query: str, *, max_results: int = 20,
                          deadline: float | None = None) -> list[str]:
    return _serpapi(query, "yandex", max_results, deadline)


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


def search_duckduckgo(query: str, *, max_results: int = 20, pause: float = 1.5,
                      deadline: float | None = None) -> list[str]:
    urls: list[str] = []
    session = requests.Session()
    for page in range(0, max_results, 25):
        if _expired(deadline):
            break
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
        time.sleep(_capped_sleep(pause, deadline))
    return urls[:max_results]


# --------------------------------------------------------------------------- #
# Реестр провайдеров и точки входа
# --------------------------------------------------------------------------- #
PROVIDERS = {
    "yandex": search_yandex,
    "google": search_google_cse,
    "serpapi_google": search_serpapi_google,
    "serpapi_yandex": search_serpapi_yandex,
    "duckduckgo": search_duckduckgo,
}

DEFAULT_PROVIDERS = ["yandex", "google"]


def search(query: str, *, provider: str = "yandex", max_results: int = 20, cache=None,
           deadline: float | None = None) -> list[str]:
    """URL по одному запросу через один провайдер (с опциональным кэшем)."""
    fn = PROVIDERS.get(provider)
    if fn is None:
        raise ValueError(f"Неизвестный провайдер поиска: {provider}")

    if cache is not None:
        cached = cache.get_search(query, provider)
        if cached is not None:
            return cached[:max_results]

    urls = fn(query, max_results=max_results, deadline=deadline)

    if cache is not None and urls:
        cache.set_search(query, provider, urls)
    return urls


def search_many(query: str, *, providers: list[str], max_results: int = 20, cache=None,
                deadline: float | None = None) -> list[str]:
    """URL по одному запросу через несколько провайдеров с объединением.

    Результаты чередуются по провайдерам (round-robin), чтобы верхние
    позиции разных движков попадали в начало списка, а дубли убираются.
    """
    per_provider = []
    for p in providers:
        if _expired(deadline):
            break
        per_provider.append(search(query, provider=p, max_results=max_results, cache=cache,
                                   deadline=deadline))
    merged: list[str] = []
    seen: set[str] = set()
    for i in range(max(len(lst) for lst in per_provider) if per_provider else 0):
        for lst in per_provider:
            if i < len(lst) and lst[i] not in seen:
                seen.add(lst[i])
                merged.append(lst[i])
    return merged
