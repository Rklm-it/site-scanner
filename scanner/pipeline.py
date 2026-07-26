"""Оркестрация: поиск → скан → оценка → список лидов."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import tldextract

from . import contacts as contacts_mod
from . import heuristics as heuristics_mod
from . import search as search_mod
from .fetcher import fetch
from .models import Lead

# Домены-агрегаторы/каталоги — это не «сайт клиента», пропускаем.
SKIP_DOMAINS = {
    "yandex.ru", "yandex.com", "google.com", "google.ru", "2gis.ru", "2gis.com",
    "avito.ru", "wikipedia.org", "youtube.com", "vk.com", "ok.ru", "instagram.com",
    "facebook.com", "t.me", "zoon.ru", "yell.ru", "flamp.ru", "otzovik.com",
    "prodoctorov.ru", "hh.ru", "rusprofile.ru", "list-org.com", "wildberries.ru",
    "ozon.ru", "dzen.ru", "pikabu.ru", "vc.ru", "habr.com", "tripadvisor.ru",
}


def registered_domain(url: str) -> str:
    ext = tldextract.extract(url)
    return ".".join(part for part in (ext.domain, ext.suffix) if part)


def collect_urls(
    queries: list[str],
    *,
    provider: str = "duckduckgo",
    max_per_query: int = 20,
) -> list[tuple[str, str]]:
    """Собирает уникальные (url, query) по всем запросам, убирая агрегаторы."""
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for query in queries:
        for url in search_mod.search(query, provider=provider, max_results=max_per_query):
            domain = registered_domain(url)
            if not domain or domain in SKIP_DOMAINS:
                continue
            if domain in seen:
                continue
            seen.add(domain)
            # Сканируем корень домена, а не глубокую страницу выдачи
            scheme = urlparse(url).scheme or "https"
            out.append((f"{scheme}://{domain}", query))
    return out


def scan_one(url: str, source_query: str | None = None) -> Lead:
    """Сканирует один сайт и собирает Lead."""
    lead = Lead(url=url, domain=registered_domain(url), source_query=source_query)
    res = fetch(url)
    lead.final_url = res.final_url
    lead.http_status = res.status
    lead.load_ms = res.load_ms
    lead.https = res.https

    if not res.ok:
        lead.error = res.error or f"HTTP {res.status}"
        return lead

    h = heuristics_mod.analyze(res.html, final_url=res.final_url or url, headers=res.headers)
    lead.outdated_score = h.outdated_score
    lead.signals = h.signals
    lead.https = h.https
    lead.mobile_friendly = h.mobile_friendly
    lead.cms = h.cms
    lead.copyright_year = h.copyright_year
    lead.title = h.title
    lead.contacts = contacts_mod.extract(res.html, base_url=res.final_url or url, title=h.title)
    return lead


def run(
    queries: list[str],
    *,
    provider: str = "duckduckgo",
    max_per_query: int = 20,
    concurrency: int = 8,
    min_score: int = 0,
    progress=None,
) -> list[Lead]:
    """Полный прогон. ``progress`` — опциональный колбэк progress(done, total)."""
    targets = collect_urls(queries, provider=provider, max_per_query=max_per_query)
    total = len(targets)
    leads: list[Lead] = []

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(scan_one, url, q): url for url, q in targets}
        for i, future in enumerate(as_completed(futures), start=1):
            try:
                leads.append(future.result())
            except Exception as exc:  # noqa: BLE001 — не роняем весь прогон из-за одного сайта
                leads.append(Lead(url=futures[future], error=f"scan failed: {exc}"))
            if progress:
                progress(i, total)

    ranked = [l for l in leads if l.error is None and l.outdated_score >= min_score]
    ranked.sort(key=lambda x: x.outdated_score, reverse=True)
    return ranked
