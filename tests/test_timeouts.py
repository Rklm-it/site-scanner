"""Предохранители от «скан висит вечно».

Каждый тест закрывает конкретное место, где прогон мог встать намертво:
разбор домена, сбор выдачи, скан сайтов, обогащение, кэш и регэкспы.
"""

import threading
import time

import pytest
import requests

import scanner.search as search_mod
from scanner import pipeline
from scanner.cache import Cache
from scanner.config import Settings
from scanner.contacts import EMAIL_RE, PHONE_RE
from scanner.fetcher import FetchResult
from scanner.models import Contacts, Lead


# --------------------------------------------------------------------------- #
# Разбор домена: tldextract не должен ходить в сеть
# --------------------------------------------------------------------------- #
def test_tldextract_never_fetches_suffix_list():
    """Список суффиксов берётся из снапшота: сетевой запрос за ним делается
    без таймаута и в закрытой сети висит вечно, вешая весь скан."""
    assert tuple(pipeline._TLD.suffix_list_urls) == ()


def test_registered_domain_offline(monkeypatch):
    """Экстрактор, настроенный как в pipeline, работает при запрещённой сети."""
    import socket

    monkeypatch.setattr(socket, "socket",
                        lambda *a, **k: pytest.fail("сеть при разборе домена"))
    fresh = pipeline.tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None,
                                           fallback_to_snapshot=True)
    ext = fresh("http://spb.example.co.uk/x")
    assert f"{ext.domain}.{ext.suffix}" == "example.co.uk"


def test_registered_domain_uses_public_suffix_list():
    """Составные суффиксы разбираются правильно — значит работает снапшот PSL,
    а не запасной разбор «две последние метки»."""
    assert pipeline.registered_domain("https://www.old-garage.ru/uslugi") == "old-garage.ru"
    assert pipeline.registered_domain("http://spb.example.co.uk/x") == "example.co.uk"
    assert pipeline._naive_domain("http://spb.example.co.uk/x") == "co.uk"   # для контраста


def test_registered_domain_survives_broken_extractor(monkeypatch):
    """Разбор домена не должен ронять прогон, что бы ни случилось внутри."""
    monkeypatch.setattr(pipeline, "_TLD", lambda url: (_ for _ in ()).throw(RuntimeError("bang")))
    assert pipeline.registered_domain("https://www.old-garage.ru/x") == "old-garage.ru"


# --------------------------------------------------------------------------- #
# Сбор выдачи
# --------------------------------------------------------------------------- #
def test_collect_passes_deadline_to_providers(monkeypatch):
    """Брошенный по бюджету поток не должен продолжать опрашивать поисковик:
    ему передаётся дедлайн, а не только таймаут пула."""
    from scanner.cache import NullCache
    seen = {}

    def fake_many(q, **kw):
        seen["deadline"] = kw.get("deadline")
        return [f"https://{q}.ru"]

    monkeypatch.setattr(pipeline.search_mod, "search_many", fake_many)
    pipeline.collect_urls(["автосервис"], providers=["yandex"], max_per_query=5,
                          cache=NullCache(), time_budget=30.0)
    assert seen["deadline"] is not None
    assert seen["deadline"] <= time.monotonic() + 30.0


def test_collect_returns_partial_on_budget(monkeypatch):
    """Один залипший запрос не крадёт всю фазу — возвращаем что успели."""
    from scanner.cache import NullCache

    def fake_many(q, **kw):
        if q == "залипший":
            time.sleep(30)
        return [f"https://{q}.ru"]

    monkeypatch.setattr(pipeline.search_mod, "search_many", fake_many)
    start = time.monotonic()
    out = pipeline.collect_urls(["быстрый", "залипший"], providers=["yandex"],
                                max_per_query=5, cache=NullCache(), time_budget=1.0)
    assert time.monotonic() - start < 10       # вышли по бюджету, а не через 30с
    assert [u for u, _ in out] == ["https://быстрый.ru"]


def test_http_raises_when_deadline_passed():
    """_http не начинает новую попытку после дедлайна (раньше повторы
    множились на таймаут и жили минутами после конца фазы)."""
    with pytest.raises(requests.exceptions.Timeout):
        search_mod._http("get", "https://example.invalid",
                         deadline=time.monotonic() - 1, timeout=20)


def test_http_stops_retrying_at_deadline(monkeypatch):
    """Сетевая ошибка + исчерпанный бюджет = ошибка сразу, без пауз и повторов."""
    calls = {"n": 0}

    def flaky(url, **kw):
        calls["n"] += 1
        raise requests.ConnectionError("нет связи")

    monkeypatch.setattr(search_mod.requests, "get", flaky)
    start = time.monotonic()
    with pytest.raises(requests.RequestException):
        search_mod._http("get", "https://example.invalid",
                         deadline=time.monotonic() + 0.2, timeout=5)
    assert time.monotonic() - start < 3
    assert calls["n"] <= 3


def test_yandex_cloud_poll_honours_deadline(monkeypatch):
    """Опрос операции ждёт по часам, а не «30 итераций по запросу каждая»."""
    monkeypatch.setattr(search_mod.time, "sleep", lambda *_: None)
    monkeypatch.setattr(search_mod, "_http",
                        lambda *a, **k: type("R", (), {"status_code": 200,
                                                       "json": lambda self: {"id": "op", "done": False}})())
    start = time.monotonic()
    got = search_mod._yandex_operation_rawdata({"id": "op", "done": False}, {},
                                               poll_timeout=30,
                                               deadline=time.monotonic() + 0.3)
    assert got is None
    assert time.monotonic() - start < 5        # 0.3с дедлайна, а не 30с poll_timeout


# --------------------------------------------------------------------------- #
# Скан сайтов
# --------------------------------------------------------------------------- #
def test_scan_one_respects_stop_flag(monkeypatch):
    """Взведённый стоп-флаг = мгновенный выход, без единого запроса."""
    monkeypatch.setattr(pipeline, "fetch",
                        lambda *a, **k: pytest.fail("запрос после остановки прогона"))
    stop = threading.Event()
    stop.set()
    lead = pipeline.scan_one("https://any.ru", politeness=pipeline.Politeness(respect_robots=False),
                             cache=pipeline.NullCache(), stop=stop)
    assert lead.error and "таймаут" in lead.error


def test_fetch_capped_by_total_budget(monkeypatch):
    """Общий потолок на загрузку: таймаут requests считается на одну операцию
    с сокетом, поэтому редиректы и http-фолбэк его обходили."""
    from scanner import fetcher

    class SlowSession:
        def get(self, url, **kw):
            time.sleep(kw.get("timeout", 1))
            raise requests.ConnectionError("зависший сайт")

    start = time.monotonic()
    res = fetcher.fetch("https://hang.ru", timeout=1.0, session=SlowSession(), max_total=1.2)
    assert time.monotonic() - start < 5        # не 2 попытки по полному таймауту
    assert not res.ok


def test_run_stops_at_total_budget(monkeypatch):
    """Общий дедлайн прогона: даже если висят все фазы, run() возвращается."""
    monkeypatch.setattr(pipeline.search_mod, "search",
                        lambda q, **kw: ["https://hang1.ru", "https://hang2.ru"])
    monkeypatch.setattr(pipeline, "fetch", lambda url, **kw: time.sleep(30))

    start = time.monotonic()
    leads = pipeline.run(Settings(queries=["x"], cache_path=None, respect_robots=False,
                                  concurrency=2, total_budget=2.0))
    assert time.monotonic() - start < 15
    assert leads == []


# --------------------------------------------------------------------------- #
# Обогащение
# --------------------------------------------------------------------------- #
def _lead_with_inn(inn: str) -> Lead:
    lead = Lead(url=f"https://{inn}.ru", domain=f"{inn}.ru")
    lead.contacts = Contacts(inn=inn)
    return lead


def test_enrich_returns_on_budget(monkeypatch):
    """Раньше пул ждали через `with` — то есть до последнего ответа реестра.
    Один залипший запрос держал скан на «Узнаю данные компаний» бесконечно."""
    from scanner.models import Enrichment

    def hangs(**kw):
        time.sleep(30)
        return Enrichment(), None

    monkeypatch.setattr(pipeline.enrich_mod, "lookup_verbose", hangs)
    leads = [_lead_with_inn("770708389%d" % i) for i in range(3)]
    prog = []

    start = time.monotonic()
    pipeline._enrich(leads, token="t", on_progress=lambda d, t: prog.append(d), budget=1.0)
    assert time.monotonic() - start < 10
    assert prog[0] == 0                        # прогресс стартовал


def test_enrich_survives_exception(monkeypatch):
    """Битый ответ по одной компании не должен ронять фазу целиком."""
    def boom(**kw):
        raise ValueError("мусор вместо JSON")

    monkeypatch.setattr(pipeline.enrich_mod, "lookup_verbose", boom)
    leads = [_lead_with_inn("7707083893")]
    pipeline._enrich(leads, token="t", budget=5.0)   # не бросает наружу


def test_enrich_stop_flag_skips_lookups(monkeypatch):
    monkeypatch.setattr(pipeline.enrich_mod, "lookup_verbose",
                        lambda **kw: pytest.fail("запрос после остановки прогона"))
    stop = threading.Event()
    stop.set()
    pipeline._enrich([_lead_with_inn("7707083893")], token="t", budget=5.0, stop=stop)


# --------------------------------------------------------------------------- #
# Кэш: брошенные потоки живут дольше прогона
# --------------------------------------------------------------------------- #
def test_cache_is_noop_after_close(tmp_path):
    """Прогон закрывает кэш по таймауту, а брошенные потоки ещё пишут в него."""
    c = Cache(str(tmp_path / "c.sqlite"), cache_pages=True)
    c.close()
    c.close()                                   # повторное закрытие безопасно
    c.mark_seen("a.ru", 50)                     # ни одна из операций не бросает
    c.set_search("q", "yandex", ["https://a.ru"])
    c.set_page(FetchResult(url="https://a.ru", status=200, html="<html>", headers={}))
    assert c.is_seen("a.ru") is False
    assert c.get_search("q", "yandex") is None
    assert c.get_page("https://a.ru") is None


# --------------------------------------------------------------------------- #
# Регэкспы: откат по длинной строке морозит процесс (re не отпускает GIL)
# --------------------------------------------------------------------------- #
def test_email_regex_linear_on_long_token():
    blob = "a" * 200_000 + " "                  # длинный «почти email» без @
    start = time.monotonic()
    EMAIL_RE.findall(blob)
    assert time.monotonic() - start < 2.0


def test_phone_regex_linear_on_separator_run():
    blob = ("8" + " " * 5_000) * 50             # цифра + гора разделителей
    start = time.monotonic()
    PHONE_RE.findall(blob)
    assert time.monotonic() - start < 2.0


def test_regexes_still_match_real_values():
    assert EMAIL_RE.findall("пишите на garage@old-garage.ru!") == ["garage@old-garage.ru"]
    assert EMAIL_RE.findall("i.van-ov+tag@mail.spb.ru") == ["i.van-ov+tag@mail.spb.ru"]
    assert PHONE_RE.findall("+7 (843) 555-00-11") == ["+7 (843) 555-00-11"]
    assert PHONE_RE.findall("8-800-555-35-35") == ["8-800-555-35-35"]
