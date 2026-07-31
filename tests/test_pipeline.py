"""End-to-end тест конвейера с замоканными поиском и загрузкой (без сети)."""

from scanner import pipeline
from scanner.config import Settings
from scanner.fetcher import FetchResult
from scanner.report import write_csv, write_json

OLD_HTML = """<html><head><title>Автосервис Гараж</title></head>
<body bgcolor="#eee">
<table width="800"><tr><td><font>Ремонт авто</font></td></tr></table>
<table width="800"><tr><td>услуги</td></tr></table>
<table width="800"><tr><td>цены</td></tr></table>
<a href="/contacts">Контакты</a>
© 2010 Гараж</body></html>"""

CONTACTS_HTML = """<html><body>
<a href="tel:+78435550011">звонок</a>
<a href="mailto:garage@old-garage.ru">почта</a>
ИНН 7707083893
</body></html>"""

MODERN_HTML = """<!DOCTYPE html><html><head><title>Новый сервис</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta property="og:title" content="Сервис"><link rel="icon" href="/f.ico">
</head><body>© 2026 Сервис</body></html>"""

PAGES = {
    "https://old-garage.ru": (OLD_HTML, "http://old-garage.ru", False),
    "http://old-garage.ru/contacts": (CONTACTS_HTML, "http://old-garage.ru/contacts", False),
    "https://modern-shop.ru": (MODERN_HTML, "https://modern-shop.ru", True),
}


def fake_search(query, *, provider, max_results=20, cache=None, **kw):
    return [
        "https://old-garage.ru/uslugi/remont",
        "https://modern-shop.ru/",
        "https://2gis.ru/kazan/firm/123",  # агрегатор — должен отсеяться
    ]


def fake_fetch(url, **kwargs):
    for base, (html, final, https) in PAGES.items():
        if url.startswith(base):
            return FetchResult(
                url=url, final_url=final, status=200,
                headers={"server": "nginx"}, html=html, load_ms=120, https=https,
            )
    return FetchResult(url=url, error="not mocked")


def _settings(**over):
    base = dict(
        queries=["автосервис Казань"], max_per_query=5, concurrency=2,
        respect_robots=False, cache_path=None, min_score=0,
    )
    base.update(over)
    return Settings(**base)


def test_pipeline_end_to_end(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline.search_mod, "search", fake_search)
    monkeypatch.setattr(pipeline, "fetch", fake_fetch)

    leads = pipeline.run(_settings())

    domains = [l.domain for l in leads]
    assert "2gis.ru" not in domains  # агрегатор отсеян
    assert domains[0] == "old-garage.ru"  # старый сайт — первым
    assert leads[0].outdated_score > leads[-1].outdated_score

    top = leads[0]
    # контакты подтянулись со страницы /contacts (follow_contact_page)
    assert top.contacts.phones and top.contacts.phones[0].startswith("+7")
    assert "garage@old-garage.ru" in top.contacts.emails
    assert top.contacts.inn == "7707083893"
    assert top.copyright_year == 2010

    csv_path = write_csv(leads, tmp_path / "leads.csv")
    json_path = write_json(leads, tmp_path / "leads.json")
    assert csv_path.exists() and csv_path.read_text(encoding="utf-8-sig").count("\n") >= 2
    assert json_path.exists()


def test_tls_error_boosts_score(monkeypatch):
    monkeypatch.setattr(pipeline.search_mod, "search",
                        lambda q, *, provider, max_results=20, cache=None, **kw: ["https://broken-ssl.ru/"])

    def broken(url, **kw):
        return FetchResult(url=url, final_url="http://broken-ssl.ru", status=200,
                           headers={}, html=MODERN_HTML, load_ms=100, https=False, tls_error=True)

    monkeypatch.setattr(pipeline, "fetch", broken)
    leads = pipeline.run(_settings(queries=["x"]))
    assert leads and leads[0].tls_error
    assert "битый SSL-сертификат" in leads[0].signals


def test_skip_seen(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline.search_mod, "search", fake_search)
    monkeypatch.setattr(pipeline, "fetch", fake_fetch)

    db = str(tmp_path / "cache.sqlite")
    first = pipeline.run(_settings(cache_path=db, skip_seen=True))
    assert first  # первый прогон что-то нашёл
    # второй прогон — те же домены уже в seen → отсеиваются
    second = pipeline.run(_settings(cache_path=db, skip_seen=True))
    assert second == []


def test_collect_reports_progress(monkeypatch):
    from scanner.cache import NullCache
    monkeypatch.setattr(pipeline.search_mod, "search_many",
                        lambda q, **k: [f"https://{q}-site.ru"])
    prog = []
    out = pipeline.collect_urls(["стоматология", "автосервис"], providers=["yandex"],
                                max_per_query=5, cache=NullCache(),
                                on_query=lambda d, t: prog.append((d, t)))
    assert prog == [(1, 2), (2, 2)]        # колбэк по каждому запросу
    assert len(out) == 2


def test_aggregator_excluded(monkeypatch):
    """Каталог/доска объявлений отсеивается по заголовку, даже если домен новый."""
    monkeypatch.setattr(pipeline.search_mod, "search",
                        lambda q, *, provider, max_results=20, cache=None, **kw: ["https://doska-new.ru/"])
    AGG = ("<html><head><title>Доска бесплатных объявлений города</title></head>"
           "<body><table width=800><tr><td>объявления</td></tr></table>© 2011</body></html>")

    def fetch_agg(url, **kw):
        return FetchResult(url=url, final_url="https://doska-new.ru", status=200,
                           headers={}, html=AGG, load_ms=100, https=True)

    monkeypatch.setattr(pipeline, "fetch", fetch_agg)
    leads = pipeline.run(_settings(queries=["x"]))
    assert leads == []          # агрегатор не попал в лиды


def test_scan_hard_timeout(monkeypatch):
    """Предохранитель: даже если сайты виснут, run() завершается по бюджету."""
    import time as _t
    monkeypatch.setattr(pipeline.search_mod, "search",
                        lambda q, *, provider, max_results=20, cache=None, **kw:
                        ["https://hang1.ru", "https://hang2.ru", "https://hang3.ru"])

    def hanging(url, **kw):
        _t.sleep(30)  # имитируем зависший сайт
        return FetchResult(url=url, error="never")

    monkeypatch.setattr(pipeline, "fetch", hanging)
    start = _t.monotonic()
    leads = pipeline.run(_settings(queries=["x"], scan_budget=1.0, concurrency=3))
    elapsed = _t.monotonic() - start
    assert elapsed < 10          # не завис на 30с, вышел по бюджету ~1с
    assert leads == []           # ничего не успело — но прогон завершился
