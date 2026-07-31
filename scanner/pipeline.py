"""Оркестрация: поиск → скан → обогащение → ранжированный список лидов."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import product
from urllib.parse import urlparse

import requests
import tldextract

from . import activity as activity_mod
from . import aggregator as aggregator_mod
from . import analytics as analytics_mod
from . import contacts as contacts_mod
from . import heuristics as heuristics_mod
from . import search as search_mod
from .cache import Cache, NullCache
from .config import Settings
from . import enrich as enrich_mod
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
    # финансовые/справочные агрегаторы и доски объявлений
    "banki.ru", "banktop.ru", "sravni.ru", "vbr.ru", "bankiros.ru", "myfin.ru",
    "unicom24.ru", "vsezaimyonline.ru", "banki-tut.ru", "creditbanking.ru",
    "domclick.ru", "cian.ru", "avito.ru", "youla.ru", "vkupiprodai.ru",
    "n1.ru", "move.ru", "mirkvartir.ru", "restate.ru", "gipernn.ru",
    "yandex.ru", "farpost.ru", "irr.ru", "from-ua.ru", "blizko.ru",
    # федеральные бренды/франшизы и афиши — ранжируются по локальным запросам,
    # но это не локальный клиент (у них свой корпоративный сайт)
    "afisha.ru", "kassir.ru", "ticketland.ru", "kudago.com", "dodopizza.ru",
    "delivery-club.ru", "kfc.ru", "papajohns.ru", "burgerking.ru", "sushiwok.ru",
    "samokat.ru", "sbermarket.ru", "vkusvill.ru", "citymobil.ru", "delivery.yandex.ru",
    "drom.ru", "auto.ru", "avito.ru",
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
    on_query=None,
    time_budget: float = 240.0,
    concurrency: int = 6,
) -> list[tuple[str, str]]:
    """Собирает уникальные (url, query), убирая агрегаторы и просмотренные домены.

    Запросы к поисковику идут ПАРАЛЛЕЛЬНО (Яндекс отвечает по несколько секунд —
    последовательно десятки запросов не укладывались в бюджет). ``on_query`` —
    прогресс, ``time_budget`` — потолок по времени на всю фазу сбора.
    """
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    total = len(queries)
    done = 0

    pool = ThreadPoolExecutor(max_workers=max(1, min(concurrency, total)))
    futures = {
        pool.submit(search_mod.search_many, q, providers=providers,
                    max_results=max_per_query, cache=cache): q
        for q in queries
    }
    try:
        for future in as_completed(futures, timeout=time_budget):
            query = futures[future]
            try:
                urls = future.result()
            except Exception as exc:  # noqa: BLE001 — не роняем сбор из-за одного запроса
                log.warning("поиск по «%s» упал: %s", query, exc)
                urls = []
            kept = 0
            for url in urls:                       # дедуп/фильтрация — в главном потоке
                domain = registered_domain(url)
                if not domain or domain in SKIP_DOMAINS or domain in seen:
                    continue
                if skip_seen and cache.is_seen(domain):
                    continue
                seen.add(domain)
                scheme = urlparse(url).scheme or "https"
                out.append((f"{scheme}://{domain}", query))
                kept += 1
            done += 1
            log.info("«%s»: выдача %d → к скану %d (агрегаторы/дубли отсеяны)", query, len(urls), kept)
            if on_query:
                on_query(done, total)
    except TimeoutError:
        log.warning("Сбор выдачи прерван по таймауту (%.0fс): обработано %d/%d запросов, доменов %d",
                    time_budget, done, total, len(out))
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
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
    want_inn: bool = False,
) -> Lead:
    """Сканирует один сайт (главная + при необходимости страница контактов).

    ``want_inn`` — при включённом обогащении заходим на «Реквизиты/Контакты»
    ещё и ради ИНН (он нужен для проверки оборота), даже если контакты уже есть.
    """
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
    lead.aggregator = aggregator_mod.aggregator_reason(
        title=h.title, company=lead.contacts.company, html=res.html)

    # Битый сертификат — сильный сигнал заброшенности
    if res.tls_error:
        lead.signals.insert(0, "битый SSL-сертификат")
        lead.outdated_score = min(100, lead.outdated_score + TLS_SIGNAL_POINTS)

    # Доходим до страницы контактов, если на главной нет контактов ИЛИ (при
    # обогащении) нет ИНН — он почти всегда на «Реквизитах», а без него не
    # узнать оборот. Без обогащения не ходим зря, чтобы не тормозить скан.
    cp = lead.contacts.contact_page
    need_more = (not lead.contacts.phones and not lead.contacts.emails) \
        or (want_inn and not lead.contacts.inn)
    if follow_contact_page and cp and cp != base and need_more:
        cres = _fetch_cached(cp, politeness=politeness, cache=cache, timeout=timeout)
        if cres.ok:
            extra = contacts_mod.extract(cres.html, base_url=cres.final_url or cp, title=h.title)
            lead.contacts.merge(extra)

    return lead


def _enrich(leads: list[Lead], token: str | None, on_progress=None) -> None:
    """Обогащение по ИНН со страницы, а при его отсутствии — по названию.

    Параллельно, чтобы десятки запросов к DaData/DataNewton не тормозили финал
    скана. ``on_progress(done, total)`` — прогресс обогащения (эта фаза долгая,
    без индикатора кажется, что скан завис).
    """
    targets = [l for l in leads if (l.contacts.inn or l.contacts.company)]
    total = len(targets)
    if on_progress:
        on_progress(0, total)

    def do(lead: Lead) -> None:
        lead.enrichment, _ = enrich_mod.lookup_verbose(
            inn=lead.contacts.inn or None, name=lead.contacts.company or None,
            ogrn=lead.contacts.ogrn or None, token=token)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(do, lead) for lead in targets]
        done = 0
        for _ in as_completed(futures):
            done += 1
            if on_progress:
                on_progress(done, total)


def run(settings: Settings, *, dadata_token: str | None = None, progress=None,
        on_collect=None, on_phase=None, on_enrich=None) -> list[Lead]:
    """Полный прогон по настройкам.

    ``progress(done, total)`` — прогресс сканирования сайтов;
    ``on_collect(done, total)`` — прогресс сбора выдачи (по запросам);
    ``on_phase(name)`` — смена фазы: collect / scan / enrich / rank;
    ``on_enrich(done, total)`` — прогресс обогащения (оборот/статус компаний).
    """
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
        if on_phase:
            on_phase("collect")
        targets = collect_urls(
            queries,
            providers=settings.providers,
            max_per_query=settings.max_per_query,
            cache=cache,
            skip_seen=settings.skip_seen,
            on_query=on_collect,
        )
        log.info("К сканированию: %d доменов из %d запросов", len(targets), len(queries))
        total = len(targets)
        leads: list[Lead] = []

        # Сразу помечаем фазу и total, чтобы UI показал «Проверяю сайты: 0/N»,
        # а не подвисал на «Собираю выдачу» до первого готового сайта.
        if on_phase:
            on_phase("scan")
        if progress:
            progress(0, total)

        # Жёсткий предохранитель: скан не может длиться дольше этого бюджета —
        # если пара сайтов зависли намертво, прогон всё равно завершится.
        budget = settings.scan_budget or \
            min(600.0, max(120.0, total * settings.timeout / max(1, settings.concurrency) * 3))
        pool = ThreadPoolExecutor(max_workers=settings.concurrency)
        futures = {
            pool.submit(
                scan_one, url, q,
                politeness=politeness, cache=cache,
                timeout=settings.timeout,
                follow_contact_page=settings.follow_contact_page,
                want_inn=settings.enrich,
            ): url
            for url, q in targets
        }
        done = 0
        try:
            for future in as_completed(futures, timeout=budget):
                try:
                    lead = future.result()
                except Exception as exc:  # noqa: BLE001 — не роняем прогон из-за одного сайта
                    lead = Lead(url=futures[future], error=f"scan failed: {exc}")
                leads.append(lead)
                done += 1
                if lead.domain:
                    cache.mark_seen(lead.domain, lead.outdated_score)
                if progress:
                    progress(done, total)
        except TimeoutError:
            log.warning("Скан прерван по таймауту %.0fс: обработано %d/%d "
                        "(остальные сайты не ответили)", budget, done, total)
        finally:
            # не ждём зависшие потоки — они сами отвалятся по таймауту сокета
            pool.shutdown(wait=False, cancel_futures=True)

        # Агрегаторы/каталоги (доски объявлений, справочники «все банки») — это
        # не клиенты, а сами каталоги. Выкидываем их из выдачи.
        aggregators = [l for l in leads if l.aggregator]
        if aggregators:
            log.info("Отсеяно агрегаторов/каталогов: %d (%s)", len(aggregators),
                     ", ".join(l.domain for l in aggregators[:8]))
        ranked = [l for l in leads
                  if l.error is None and not l.aggregator
                  and l.outdated_score >= settings.min_score]

        if settings.enrich:
            log.info("Обогащение по ИНН: %d лидов", len(ranked))
            if on_phase:
                on_phase("enrich")
            _enrich(ranked, dadata_token, on_progress=on_enrich)

        # Аналитика аутрича и сортировка по приоритету «кому писать»
        if on_phase:
            on_phase("rank")
        analytics_mod.annotate(ranked)
        ranked.sort(key=lambda x: (x.outreach_score, x.outdated_score), reverse=True)

        return ranked
    finally:
        cache.close()
