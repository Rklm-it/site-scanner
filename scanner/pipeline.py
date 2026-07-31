"""Оркестрация: поиск → скан → обогащение → ранжированный список лидов."""

from __future__ import annotations

import logging
import threading
import time
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

# Потолки времени на фазы (сек). Без них любая внешняя зависимость (поисковик,
# DaData, зависший сайт) держит прогон бесконечно, и в UI скан «висит вечно».
DEFAULT_TOTAL_BUDGET = 1800.0     # весь прогон целиком
DEFAULT_COLLECT_BUDGET = 240.0    # сбор выдачи
DEFAULT_ENRICH_BUDGET = 600.0     # обогащение (DaData/DataNewton)

# ВАЖНО: tldextract по умолчанию при первом вызове тянет из сети публичный
# список суффиксов (PSL) — и делает это БЕЗ таймаута (cache_fetch_timeout=None).
# Если сеть режется молча (фаервол/прокси дропает пакеты), extract() блокируется
# навсегда, а вместе с ним и весь скан: registered_domain() дёргается и в главном
# потоке сбора выдачи, где его не прикрывает ни один бюджет. Плюс поход за PSL
# сериализуется файловым локом — вешает сразу все потоки.
# Нам такой точности не нужно: берём снапшот, вшитый в пакет (офлайн, мгновенно,
# детерминированно). suffix_list_urls=() отключает сеть, cache_dir=None — диск.
_TLD = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None, fallback_to_snapshot=True)


def _naive_domain(url: str) -> str:
    """Запасной разбор домена, если tldextract почему-то не сработал."""
    host = urlparse(url if "//" in url else f"//{url}").netloc
    host = host.rsplit("@", 1)[-1].split(":", 1)[0].strip().strip(".").lower()
    parts = [p for p in host.split(".") if p]
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def registered_domain(url: str) -> str:
    try:
        ext = _TLD(url)
    except Exception as exc:  # noqa: BLE001 — разбор домена не должен ронять прогон
        log.debug("tldextract не разобрал %s (%s) — запасной разбор", url, exc)
        return _naive_domain(url)
    return ".".join(part for part in (ext.domain, ext.suffix) if part)


def _left(deadline: float | None, *, floor: float = 0.05) -> float | None:
    """Сколько секунд осталось до дедлайна (None — дедлайна нет)."""
    if deadline is None:
        return None
    return max(floor, deadline - time.monotonic())


def _stopped(stop: threading.Event | None) -> bool:
    return stop is not None and stop.is_set()


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
    time_budget: float = DEFAULT_COLLECT_BUDGET,
    concurrency: int = 6,
    stop: threading.Event | None = None,
) -> list[tuple[str, str]]:
    """Собирает уникальные (url, query), убирая агрегаторы и просмотренные домены.

    Запросы к поисковику идут ПАРАЛЛЕЛЬНО (Яндекс отвечает по несколько секунд —
    последовательно десятки запросов не укладывались в бюджет). ``on_query`` —
    прогресс, ``time_budget`` — потолок по времени на всю фазу сбора.

    Тот же ``time_budget`` уходит внутрь провайдеров дедлайном: иначе поток,
    брошенный по таймауту фазы, продолжал бы часами опрашивать Яндекс (у Cloud
    v2 опрос операции + повторы дают до получаса на один запрос) и жёг квоту.
    """
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    total = len(queries)
    done = 0
    deadline = time.monotonic() + time_budget

    pool = ThreadPoolExecutor(max_workers=max(1, min(concurrency, total)))
    futures = {
        pool.submit(search_mod.search_many, q, providers=providers,
                    max_results=max_per_query, cache=cache, deadline=deadline): q
        for q in queries
    }
    try:
        for future in as_completed(futures, timeout=_left(deadline)):
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
        log.warning("Сбор выдачи прерван по таймауту (%.0fс): обработано %d/%d запросов, доменов %d. "
                    "Обычно это молчащий поисковик — проверьте ключ и лимиты в «API-ключи».",
                    time_budget, done, total, len(out))
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return out


def _fetch_cached(url: str, *, politeness: Politeness, cache, timeout: float,
                  stop: threading.Event | None = None):
    from .fetcher import FetchResult

    cached = cache.get_page(url)
    if cached is not None:
        return cached
    if _stopped(stop):
        return FetchResult(url=url, error="прогон остановлен по таймауту")
    if not politeness.allowed(url):
        log.debug("robots.txt запрещает %s", url)
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
    stop: threading.Event | None = None,
) -> Lead:
    """Сканирует один сайт (главная + при необходимости страница контактов).

    ``want_inn`` — при включённом обогащении заходим на «Реквизиты/Контакты»
    ещё и ради ИНН (он нужен для проверки оборота), даже если контакты уже есть.
    ``stop`` — общий стоп-флаг прогона: выставляется, когда фаза вышла из бюджета,
    чтобы брошенные потоки не тянули ещё по запросу каждый.
    """
    lead = Lead(url=url, domain=registered_domain(url), source_query=source_query)
    if _stopped(stop):
        lead.error = "прогон остановлен по таймауту"
        return lead
    res = _fetch_cached(url, politeness=politeness, cache=cache, timeout=timeout, stop=stop)
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
    if follow_contact_page and cp and cp != base and need_more and not _stopped(stop):
        cres = _fetch_cached(cp, politeness=politeness, cache=cache, timeout=timeout, stop=stop)
        if cres.ok:
            extra = contacts_mod.extract(cres.html, base_url=cres.final_url or cp, title=h.title)
            lead.contacts.merge(extra)

    return lead


def _enrich(leads: list[Lead], token: str | None, on_progress=None,
            *, budget: float | None = None, stop: threading.Event | None = None) -> None:
    """Обогащение по ИНН со страницы, а при его отсутствии — по названию.

    Параллельно, чтобы десятки запросов к DaData/DataNewton не тормозили финал
    скана. ``on_progress(done, total)`` — прогресс обогащения (эта фаза долгая,
    без индикатора кажется, что скан завис).

    ``budget`` — потолок по времени на всю фазу. Раньше его не было вовсе: пул
    ждали через ``with``, то есть до последнего ответа. Один залипший запрос к
    реестру — и прогон стоял на «Узнаю данные компаний» бесконечно, потому что
    таймаут requests считается на отдельную операцию с сокетом, а не на запрос
    целиком (редиректы и «струйка» байт его обходят).
    """
    targets = []
    for lead in leads:
        if lead.contacts.inn or lead.contacts.company:
            targets.append(lead)
        else:
            # Искать компанию не по чему — так и пишем, вместо пустой ячейки.
            lead.enrichment.note = "на сайте нет ни ИНН, ни названия компании — не по чему искать"
    total = len(targets)
    if on_progress:
        on_progress(0, total)
    if not total:
        return

    def do(lead: Lead) -> None:
        if _stopped(stop):
            return
        try:
            # Причина пустого оборота лежит в enrichment.note — раньше она
            # терялась, и в таблице был просто пустой прочерк без объяснений.
            lead.enrichment, _ = enrich_mod.lookup_verbose(
                inn=lead.contacts.inn or None, name=lead.contacts.company or None,
                ogrn=lead.contacts.ogrn or None, token=token)
        except Exception as exc:  # noqa: BLE001 — один битый ответ не рушит фазу
            log.warning("обогащение %s упало: %s", lead.domain, exc)

    pool = ThreadPoolExecutor(max_workers=8)
    futures = [pool.submit(do, lead) for lead in targets]
    done = 0
    try:
        for _ in as_completed(futures, timeout=budget):
            done += 1
            if on_progress:
                on_progress(done, total)
    except TimeoutError:
        log.warning("Обогащение прервано по таймауту (%.0fс): успели %d/%d компаний — "
                    "у остальных оборот/статус останутся пустыми", budget or 0, done, total)
        if stop is not None:
            stop.set()          # брошенные потоки не должны дальше жечь лимит API
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def run(settings: Settings, *, dadata_token: str | None = None, progress=None,
        on_collect=None, on_phase=None, on_enrich=None) -> list[Lead]:
    """Полный прогон по настройкам.

    ``progress(done, total)`` — прогресс сканирования сайтов;
    ``on_collect(done, total)`` — прогресс сбора выдачи (по запросам);
    ``on_phase(name)`` — смена фазы: collect / scan / enrich / rank;
    ``on_enrich(done, total)`` — прогресс обогащения (оборот/статус компаний).

    У прогона есть общий дедлайн (``settings.total_budget``): каждая фаза берёт
    не больше своего бюджета И не больше остатка от общего. Так прогон всегда
    заканчивается — с частичным результатом и предупреждением, но заканчивается.
    """
    queries = expand_queries(settings)
    if not queries:
        raise ValueError("Не задано ни одного запроса (queries/categories).")

    deadline = time.monotonic() + (settings.total_budget or DEFAULT_TOTAL_BUDGET)
    # Стоп-флаги отдельные на фазу: таймаут скана не должен гасить обогащение
    # уже собранных лидов. Оба взводятся на выходе из run(), чтобы брошенные
    # потоки не жили дольше самого прогона.
    scan_stop = threading.Event()
    enrich_stop = threading.Event()

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
            time_budget=min(settings.collect_budget or DEFAULT_COLLECT_BUDGET,
                            _left(deadline)),
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
        # Обогащению оставляем его долю общего дедлайна, иначе скан съест всё.
        budget = settings.scan_budget or \
            min(600.0, max(120.0, total * settings.timeout / max(1, settings.concurrency) * 3))
        reserve = (settings.enrich_budget or DEFAULT_ENRICH_BUDGET) if settings.enrich else 0.0
        budget = min(budget, max(10.0, _left(deadline) - reserve))
        pool = ThreadPoolExecutor(max_workers=settings.concurrency)
        futures = {
            pool.submit(
                scan_one, url, q,
                politeness=politeness, cache=cache,
                timeout=settings.timeout,
                follow_contact_page=settings.follow_contact_page,
                want_inn=settings.enrich,
                stop=scan_stop,
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
            scan_stop.set()
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
            _enrich(ranked, dadata_token, on_progress=on_enrich,
                    budget=min(settings.enrich_budget or DEFAULT_ENRICH_BUDGET, _left(deadline)),
                    stop=enrich_stop)

        # Аналитика аутрича и сортировка по приоритету «кому писать»
        if on_phase:
            on_phase("rank")
        analytics_mod.annotate(ranked)
        ranked.sort(key=lambda x: (x.outreach_score, x.outdated_score), reverse=True)

        return ranked
    finally:
        # Прогон закончился — брошенные по таймауту потоки должны свернуться,
        # а не ходить в сеть параллельно со следующим сканом.
        scan_stop.set()
        enrich_stop.set()
        cache.close()
