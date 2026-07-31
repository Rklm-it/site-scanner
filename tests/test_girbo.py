"""Тесты оборота через ГИР БО (bo.nalog.gov.ru) — без сети.

Фикстуры взяты с живого API: ООО «ГЕПАРД», ИНН 0263029296, id 11141031.
"""

from scanner import girbo

SEARCH_HIT = {
    "content": [{"id": 11141031, "inn": "0263029296",
                 "shortName": 'ООО "<strong>ГЕПАРД</strong>"'}],
    "totalElements": 1,
}
SEARCH_EMPTY = {"content": [], "totalElements": 0}

# gainSum — это строка 2110 «Выручка» (сверено с financialResult.current2110)
BFO_LIST = [
    {"id": 29422162, "period": "2025", "gainSum": 1980674, "actives": 1762371.0},
    {"id": 25026595, "period": "2024", "gainSum": 3061980},
    {"id": 21868192, "period": "2023", "gainSum": 2763036},
]


class FakeResp:
    def __init__(self, payload=None, status=200):
        self.status_code = status
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("не-JSON")
        return self._payload


class FakeSession:
    """Отдаёт ответы по порядку и запоминает, куда ходили."""

    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls = []

    def get(self, url, **kw):
        self.calls.append((url, kw.get("params")))
        return self._responses.pop(0) if self._responses else FakeResp(status=500)


def test_latest_revenue_takes_newest_year_in_rubles():
    # 1 980 674 тыс.руб за 2025 → 1 980 674 000 руб
    assert girbo.latest_revenue(BFO_LIST) == 1_980_674_000


def test_latest_revenue_ignores_empty_and_zero():
    assert girbo.latest_revenue([{"period": "2024", "gainSum": 0},
                                 {"period": "н/д", "gainSum": 5}]) is None
    assert girbo.latest_revenue([]) is None


def test_revenue_by_inn_ok():
    sess = FakeSession(FakeResp(SEARCH_HIT), FakeResp(BFO_LIST))
    rev, err = girbo.revenue_by_inn("0263029296", session=sess)
    assert rev == 1_980_674_000 and err is None
    # поиск по ИНН, затем отчётность найденной организации
    assert sess.calls[0][1] == {"query": "0263029296", "page": 0}
    assert sess.calls[1][0].endswith("/nbo/organizations/11141031/bfo/")


def test_revenue_by_inn_not_found():
    sess = FakeSession(FakeResp(SEARCH_EMPTY))
    rev, err = girbo.revenue_by_inn("7707083893", session=sess)
    assert rev is None and "не найдена в ГИР БО" in err
    assert len(sess.calls) == 1        # за отчётностью не ходим впустую


def test_revenue_by_inn_rejects_foreign_match():
    """Поиск понимает и название, поэтому чужой ИНН в ответе брать нельзя."""
    other = {"content": [{"id": 999, "inn": "7712345678", "shortName": "ООО Другое"}]}
    rev, err = girbo.revenue_by_inn("0263029296", session=FakeSession(FakeResp(other)))
    assert rev is None and "совпадения по ИНН нет" in err


def test_revenue_by_inn_company_without_reports():
    sess = FakeSession(FakeResp(SEARCH_HIT), FakeResp([]))
    rev, err = girbo.revenue_by_inn("0263029296", session=sess)
    assert rev is None and "отчётность не сдавала" in err


def test_revenue_by_inn_http_error():
    rev, err = girbo.revenue_by_inn("0263029296", session=FakeSession(FakeResp(status=503)))
    assert rev is None and "503" in err


def test_revenue_by_inn_skips_without_inn():
    assert girbo.revenue_by_inn("") == (None, None)


def test_clean_strips_search_highlight():
    assert girbo._clean('ООО "<strong>ГЕПАРД</strong>"') == 'ООО "ГЕПАРД"'


def test_enrich_prefers_girbo_over_datanewton(monkeypatch):
    """ГИР БО бесплатен и без лимитов — к DataNewton идём только если он молчит."""
    import scanner.enrich as m

    monkeypatch.setattr(m, "_dadata_post", lambda *a: ({"suggestions": [{"data": {
        "inn": "0263029296", "name": {"short_with_opf": 'ООО "ГЕПАРД"'}}}]}, None))
    monkeypatch.setattr(m.girbo, "revenue_by_inn", lambda i, **kw: (1_980_674_000, None))
    monkeypatch.setattr(m.datanewton, "revenue_by_inn",
                        lambda i, **kw: (_ for _ in ()).throw(AssertionError("лишний запрос")))

    e, err = m.lookup_verbose(inn="0263029296", token="x", dn_token="dn")
    assert e.revenue == 1_980_674_000 and err is None and e.note is None


def test_enrich_falls_back_to_datanewton(monkeypatch):
    import scanner.enrich as m

    monkeypatch.setattr(m, "_dadata_post", lambda *a: ({"suggestions": [{"data": {
        "inn": "0263029296", "name": {"short_with_opf": 'ООО "ГЕПАРД"'}}}]}, None))
    monkeypatch.setattr(m.girbo, "revenue_by_inn", lambda i, **kw: (None, "нет в ГИР БО"))
    monkeypatch.setattr(m.datanewton, "revenue_by_inn", lambda i, **kw: (44_000_000, None))

    e, _ = m.lookup_verbose(inn="0263029296", token="x", dn_token="dn")
    assert e.revenue == 44_000_000


def test_enrich_works_without_dadata_key(monkeypatch):
    """Оборот достижим и вовсе без ключей: ГИР БО ходит по ИНН со страницы."""
    import scanner.enrich as m

    monkeypatch.delenv("DADATA_TOKEN", raising=False)
    monkeypatch.delenv("DATANEWTON_TOKEN", raising=False)
    monkeypatch.setattr(m.girbo, "revenue_by_inn", lambda i, **kw: (1_980_674_000, None))

    e, err = m.lookup_verbose(inn="0263029296")
    assert e.revenue == 1_980_674_000
