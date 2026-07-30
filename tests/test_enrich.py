from scanner.enrich import parse_party, enrich_by_inn, enrich_by_name, lookup

DADATA_DATA = {
    "name": {"short_with_opf": "ООО \"Ромашка\"", "full_with_opf": "Общество ..."},
    "state": {"status": "ACTIVE", "registration_date": 1262304000000},  # 2010-01-01
    "finance": {"income": 15000000, "expense": 12000000},
    "employee_count": 42,
    "management": {"name": "Иванов Иван Иванович", "post": "Директор"},
    "address": {"value": "г Казань, ул Баумана, д 1"},
}


def test_parse_party():
    e = parse_party(DADATA_DATA)
    assert e.official_name == 'ООО "Ромашка"'
    assert e.status == "ACTIVE"
    assert e.revenue == 15000000
    assert e.employee_count == 42
    assert e.management == "Иванов Иван Иванович"
    assert e.registration_date == "2010-01-01"
    assert "Казань" in e.address


def test_parse_party_partial():
    e = parse_party({"name": {"short_with_opf": "ИП Петров"}})
    assert e.official_name == "ИП Петров"
    assert e.revenue is None
    assert e.status is None


def test_enrich_without_token(monkeypatch):
    import scanner.enrich as enrich_mod
    monkeypatch.delenv("DADATA_TOKEN", raising=False)
    enrich_mod._warned = False
    e = enrich_by_inn("7707083893", token=None)
    assert e.revenue is None and e.official_name is None


class FakeResp:
    status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return {"suggestions": [{"data": DADATA_DATA}]}


class FakeSession:
    def post(self, *a, **k):
        return FakeResp()


def test_enrich_with_mocked_api():
    e = enrich_by_inn("7707083893", token="x", session=FakeSession())
    assert e.revenue == 15000000
    assert e.official_name == 'ООО "Ромашка"'


def test_enrich_by_name():
    e = enrich_by_name("ООО Ромашка Казань", token="x", session=FakeSession())
    assert e.revenue == 15000000
    assert e.official_name == 'ООО "Ромашка"'


def test_lookup_falls_back_to_name(monkeypatch):
    import scanner.enrich as m
    monkeypatch.delenv("DATANEWTON_TOKEN", raising=False)

    def fake_post(url, payload, token, session):
        if url == m.DADATA_URL:                      # по ИНН — пусто
            return {"suggestions": []}, None
        return {"suggestions": [{"data": {          # по названию — нашли
            "name": {"short_with_opf": "Найдено"}, "finance": {"income": 999}}}]}, None

    monkeypatch.setattr(m, "_dadata_post", fake_post)
    e = lookup(inn="123", name="ООО Тест", token="x")
    assert e.revenue == 999 and e.official_name == "Найдено"


def test_lookup_gets_revenue_from_datanewton(monkeypatch):
    """DaData даёт название/директора, DataNewton — оборот по резолвнутому ИНН."""
    import scanner.enrich as m

    def fake_post(url, payload, token, session):     # DaData: название + ИНН, без оборота
        return {"suggestions": [{"data": {
            "name": {"short_with_opf": "ООО Ромашка"},
            "management": {"name": "Иванов Иван Иванович"},
            "inn": "7707083893"}}]}, None

    monkeypatch.setattr(m, "_dadata_post", fake_post)
    monkeypatch.setattr(m.datanewton, "revenue_by_inn",
                        lambda inn, **k: (44_000_000, None) if inn == "7707083893" else (None, None))
    e, err = m.lookup_verbose(name="ООО Ромашка", token="x", dn_token="dn")
    assert e.official_name == "ООО Ромашка"
    assert e.management == "Иванов Иван Иванович"
    assert e.revenue == 44_000_000          # оборот добрался из DataNewton
    assert err is None


def test_lookup_revenue_without_dadata(monkeypatch):
    """Оборот работает даже без DaData, если ИНН есть со страницы."""
    import scanner.enrich as m
    monkeypatch.delenv("DADATA_TOKEN", raising=False)
    monkeypatch.setattr(m.datanewton, "revenue_by_inn", lambda inn, **k: (7_000_000, None))
    e, err = m.lookup_verbose(inn="7707083893", token=None, dn_token="dn")
    assert e.revenue == 7_000_000
