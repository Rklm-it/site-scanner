"""Оркестрация: поиск → скан → обогащение → ранжированный список лидов."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import product
from urllib.parse import urlparse

import requests
import tldextract

from . import activity as activity_mod
from . import analytics as analytics_mod
from . import contacts as contacts_mod
from . import heuristics as heuristics_mod
from . import search as search_mod
from .cache import Cache, NullCache
from .config import Settings
from .enrich import enrich_by_inn
from .fetcher import fetch
from .models import Lead
from .politeness import Politeness

log = logging.getLogger("scanner")

# Домены-агрегаторы/каталоги — это не «сайт клиента», пропускаем.
SKIP_DOMAINS = {
    "yandex.ru", "yandex.com", "ya.ru", "google.com", "google.ru", "2gis.ru", "2gis.com",
    "avito.ru", "wikipedia.org", "youtube.com", "vk.com", "vk.ru", "vkontakte.ru",
    "ok.ru", "instagram.com", "facebook.com", "t.me", "telegram.org", "wa.me",
    "whatsapp.com", "twitter.com", "x.com", "rutube.ru", "livejournal.com",
    "zoon.ru", "yell.ru", "flamp.ru", "otzovik.com", "irecommend.ru", "otzyvru.com",
    "prodoctorov.ru", "docdoc.ru", "napopravku.ru", "sberhealth.ru",
    "hh.ru", "rabota.ru", "superjob.ru", "avito.ru", "youla.ru",
    "rusprofile.ru", "list-org.com", "sbis.ru", "checko.ru", "audit-it.ru",
    "wildberries.ru", "ozon.ru", "aliexpress.ru", "market.yandex.ru", "megamarket.ru",
    "dzen.ru", "zen.yandex.ru", "pikabu.ru", "vc.ru", "habr.com", "tripadvisor.ru",
    "maps.yandex.ru", "blizko.ru", "spr.ru", "orgpage.ru", "yandex.by", "mail.ru",
    "tiu.ru", "pulscen.ru", "regmarkets.ru", "satom.ru", "flampp.ru", "zoon.com",
}

TLS_SIGNAL_POINTS = 18


def registered_domain(url: str) -> str:
    ext = tldextract.extract(url)
    return ".".join(part for part in (ext.domain, ext.suffix) if part)


def expand_queries(settings: Settings) -> list[str]:
    """Собирает финальный список запросов: явные + «категория × город»."""
    queries = list(settings.queries)
    if settings.categories:
        cities = settings.cities or [""]
        for category, city in product(settings.categories, cities):
            queries.append(f"{category} {city}".strip())
    return list(dict.fromkeys(q for q in queries if q))


def collect_urls(
    queries: list[str],
    *,
    providers: list[str],
    max_per_query: int,
    cache,
    skip_seen: bool = False,
) -> list[tuple[str, str]]:
    """Собирает уникальные (url, query), убирая агрегаторы и просмотренные домены."""
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for query in queries:
        urls = search_mod.search_many(query, providers=providers, max_results=max_per_query, cache=cache)
        kept = 0
        for url in urls:
            domain = registered_domain(url)
            if not domain or domain in SKIP_DOMAINS or domain in seen:
                continue
            if skip_seen and cache.is_seen(domain):
                continue
            seen.add(domain)
            scheme = urlparse(url).scheme or "https"
            out.append((f"{scheme}://{domain}", query))
            kept += 1
        log.info("«%s»: выдача %d → к скану %d (агрегаторы/дубли отсеяны)", query, len(urls), kept)
    return out


def _fetch_cached(url: str, *, politeness: Politeness, cache, timeout: float):
    cached = cache.get_page(url)
    if cached is not None:
        return cached
    if not politeness.allowed(url):
        log.debug("robots.txt запрещает %s", url)
        from .fetcher import FetchResult
        return FetchResult(url=url, error="disallowed by robots.txt")
    politeness.wait(url)
    res = fetch(url, timeout=timeout)
    cache.set_page(res)
    return res


def scan_one(
    url: str,
    source_query: str | None = None,
    *,
    politeness: Politeness,
    cache,
    timeout: float = 12.0,
    follow_contact_page: bool = True,
) -> Lead:
    """Сканирует один сайт (главная + при необходимости страница контактов)."""
    lead = Lead(url=url, domain=registered_domain(url), source_query=source_query)
    res = _fetch_cached(url, politeness=politeness, cache=cache, timeout=timeout)
    lead.final_url = res.final_url
    lead.http_status = res.status
    lead.load_ms = res.load_ms
    lead.https = res.https
    lead.tls_error = res.tls_error

    if not res.ok:
        lead.error = res.error or f"HTTP {res.status}"
        return lead

    base = res.final_url or url
    h = heuristics_mod.analyze(res.html, final_url=base, headers=res.headers)
    lead.outdated_score = h.outdated_score
    lead.signals = h.signals
    lead.https = h.https
    lead.mobile_friendly = h.mobile_friendly
    lead.cms = h.cms
    lead.copyright_year = h.copyright_year
    lead.title = h.title
    lead.contacts = contacts_mod.extract(res.html, base_url=base, title=h.title)
    lead.marketing = activity_mod.detect(res.html)

    # Битый сертификат — сильный сигнал заброшенности
    if res.tls_error:
        lead.signals.insert(0, "битый SSL-сертификат")
        lead.outdated_score = min(100, lead.outdated_score + TLS_SIGNAL_POINTS)

    # Доходим до страницы контактов за телефонами/ИНН, если их мало
    cp = lead.contacts.contact_page
    need_more = not lead.contacts.phones or not lead.contacts.inn
    if follow_contact_page and cp and cp != base and need_more:
        cres = _fetch_cached(cp, politeness=politeness, cache=cache, timeout=timeout)
        if cres.ok:
            extra = contacts_mod.extract(cres.html, base_url=cres.final_url or cp, title=h.title)
            lead.contacts.merge(extra)

    return lead


def _enrich(leads: list[Lead], token: str | None) -> None:
    session = requests.Session()
    for lead in leads:
        if lead.contacts.inn:
            lead.enrichment = enrich_by_inn(lead.contacts.inn, token=token, session=session)


def run(settings: Settings, *, dadata_token: str | None = None, progress=None) -> list[Lead]:
    """Полный прогон по настройкам. ``progress`` — колбэк progress(done, total)."""
    queries = expand_queries(settings)
    if not queries:
        raise ValueError("Не задано ни одного запроса (queries/categories).")

    if settings.cache_path:
        cache = Cache(
            settings.cache_path,
            search_ttl=settings.search_ttl,
            page_ttl=settings.page_ttl,
            cache_pages=settings.cache_pages,
        )
    else:
        cache = NullCache()

    politeness = Politeness(
        respect_robots=settings.respect_robots,
        per_host_delay=settings.per_host_delay,
    )

    try:
        targets = collect_urls(
            queries,
            providers=settings.providers,
            max_per_query=settings.max_per_query,
            cache=cache,
            skip_seen=settings.skip_seen,
        )
        log.info("К сканированию: %d доменов из %d запросов", len(targets), len(queries))
        total = len(targets)
        leads: list[Lead] = []

        with ThreadPoolExecutor(max_workers=settings.concurrency) as pool:
            futures = {
                pool.submit(
                    scan_one, url, q,
                    politeness=politeness, cache=cache,
                    timeout=settings.timeout,
                    follow_contact_page=settings.follow_contact_page,
                ): url
                for url, q in targets
            }
            for i, future in enumerate(as_completed(futures), start=1):
                try:
                    lead = future.result()
                except Exception as exc:  # noqa: BLE001 — не роняем прогон из-за одного сайта
                    lead = Lead(url=futures[future], error=f"scan failed: {exc}")
                leads.append(lead)
                if lead.domain:
                    cache.mark_seen(lead.domain, lead.outdated_score)
                if progress:
                    progress(i, total)

        ranked = [l for l in leads if l.error is None and l.outdated_score >= settings.min_score]

        if settings.enrich:
            log.info("Обогащение по ИНН: %d лидов", len(ranked))
            _enrich(ranked, dadata_token)

        # Аналитика аутрича и сортировка по приоритету «кому писать»
        analytics_mod.annotate(ranked)
        ranked.sort(key=lambda x: (x.outreach_score, x.outdated_score), reverse=True)

        return ranked
    finally:
        cache.close()
