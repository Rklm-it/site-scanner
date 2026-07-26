"""End-to-end тест конвейера с замоканными поиском и загрузкой (без сети)."""

from scanner import pipeline
from scanner.fetcher import FetchResult
from scanner.report import write_csv, write_json

OLD_HTML = """<html><head><title>Автосервис Гараж</title></head>
<body bgcolor="#eee">
<table width="800"><tr><td><font>Ремонт авто</font></td></tr></table>
<table width="800"><tr><td>услуги</td></tr></table>
<table width="800"><tr><td>цены</td></tr></table>
<a href="tel:+78435550011">звонок</a>
<a href="mailto:garage@old-garage.ru">почта</a>
© 2010 Гараж</body></html>"""

MODERN_HTML = """<!DOCTYPE html><html><head><title>Новый сервис</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta property="og:title" content="Сервис"><link rel="icon" href="/f.ico">
</head><body>© 2026 Сервис</body></html>"""

PAGES = {
    "https://old-garage.ru": (OLD_HTML, "http://old-garage.ru", False),
    "https://modern-shop.ru": (MODERN_HTML, "https://modern-shop.ru", True),
}


def fake_search(query, *, provider="duckduckgo", max_results=20):
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


def test_pipeline_end_to_end(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline.search_mod, "search", fake_search)
    monkeypatch.setattr(pipeline, "fetch", fake_fetch)

    leads = pipeline.run(["автосервис Казань"], max_per_query=5, concurrency=2)

    domains = [l.domain for l in leads]
    assert "2gis.ru" not in domains  # агрегатор отсеян
    assert domains[0] == "old-garage.ru"  # старый сайт — первым
    assert leads[0].outdated_score > leads[-1].outdated_score

    top = leads[0]
    assert top.contacts.phones and top.contacts.phones[0].startswith("+7")
    assert "garage@old-garage.ru" in top.contacts.emails
    assert top.copyright_year == 2010

    csv_path = write_csv(leads, tmp_path / "leads.csv")
    json_path = write_json(leads, tmp_path / "leads.json")
    assert csv_path.exists() and csv_path.read_text(encoding="utf-8-sig").count("\n") >= 2
    assert json_path.exists()
