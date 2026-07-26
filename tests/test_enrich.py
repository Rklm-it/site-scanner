from scanner.enrich import parse_party, enrich_by_inn

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


def test_enrich_with_mocked_api(monkeypatch):
    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"suggestions": [{"data": DADATA_DATA}]}

    class FakeSession:
        def post(self, *a, **k):
            return FakeResp()

    e = enrich_by_inn("7707083893", token="x", session=FakeSession())
    assert e.revenue == 15000000
    assert e.official_name == 'ООО "Ромашка"'
