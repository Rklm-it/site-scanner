"""Тесты поисковых провайдеров и объединения выдачи (без сети)."""

import base64

import scanner.search as search_mod

YANDEX_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<yandexsearch version="1.0"><response><results><grouping>
<group><doc><url>https://garage-old.ru/</url></doc></group>
<group><doc><url>https://stoma-kzn.ru/</url></doc></group>
</grouping></results></response></yandexsearch>"""

YANDEX_EMPTY = b"""<?xml version="1.0" encoding="utf-8"?>
<yandexsearch version="1.0"><response><results><grouping>
</grouping></results></response></yandexsearch>"""

YANDEX_ERR = b"""<?xml version="1.0" encoding="utf-8"?>
<yandexsearch version="1.0"><response>
<error code="55">Bad key</error></response></yandexsearch>"""


class FakeResp:
    def __init__(self, content=b"", status=200):
        self.content = content
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise search_mod.requests.HTTPError(str(self.status_code))


def test_yandex_xml_parsing(monkeypatch):
    monkeypatch.setenv("YANDEX_XML_USER", "u")
    monkeypatch.setenv("YANDEX_XML_KEY", "k")

    def fake_get(*a, **k):
        # первая страница — с результатами, следующие — пустые (как у API)
        page = int(k.get("params", {}).get("page", 0))
        return FakeResp(YANDEX_XML if page == 0 else YANDEX_EMPTY)

    monkeypatch.setattr(search_mod.requests, "get", fake_get)

    urls = search_mod.search_yandex_xml("автосервис Казань", max_results=10)
    assert urls == ["https://garage-old.ru/", "https://stoma-kzn.ru/"]


def test_yandex_missing_credentials(monkeypatch):
    for var in ("YANDEX_API_KEY", "YANDEX_FOLDER_ID", "YANDEX_XML_USER", "YANDEX_XML_KEY"):
        monkeypatch.delenv(var, raising=False)
    search_mod._warned.clear()
    assert search_mod.search_yandex_xml("что угодно") == []


def test_yandex_api_error(monkeypatch):
    monkeypatch.setenv("YANDEX_XML_USER", "u")
    monkeypatch.setenv("YANDEX_XML_KEY", "k")
    monkeypatch.setattr(search_mod.requests, "get", lambda *a, **k: FakeResp(YANDEX_ERR))
    search_mod._warned.clear()
    assert search_mod.search_yandex_xml("что угодно") == []


class FakeJsonResp:
    def __init__(self, payload, status=200, text=""):
        self._payload = payload
        self.status_code = status
        self.text = text

    def json(self):
        return self._payload


def test_yandex_cloud_parsing(monkeypatch):
    monkeypatch.setenv("YANDEX_API_KEY", "apikey")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1gfolder")
    search_mod._warned.clear()

    def fake_http(method, url, **k):
        assert method == "post" and url == search_mod.YANDEX_CLOUD
        assert k["headers"]["Authorization"] == "Api-Key apikey"
        page = int(k["json"]["query"]["page"])
        raw = YANDEX_XML if page == 0 else YANDEX_EMPTY
        return FakeJsonResp({"rawData": base64.b64encode(raw).decode()})

    monkeypatch.setattr(search_mod, "_http", fake_http)
    urls = search_mod.search_yandex_cloud("автосервис Казань", max_results=10)
    assert urls == ["https://garage-old.ru/", "https://stoma-kzn.ru/"]


def test_yandex_cloud_http_error(monkeypatch):
    monkeypatch.setenv("YANDEX_API_KEY", "apikey")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1gfolder")
    search_mod._warned.clear()
    monkeypatch.setattr(search_mod, "_http",
                        lambda *a, **k: FakeJsonResp({}, status=401, text="unauthorized"))
    assert search_mod.search_yandex_cloud("q") == []


def test_yandex_dispatcher_classic_first(monkeypatch):
    """С apikey+folder сначала пробуется классический endpoint; если он вернул
    результаты — Cloud v2 не дёргается."""
    for v in ("YANDEX_API_KEY", "YANDEX_FOLDER_ID", "YANDEX_XML_USER", "YANDEX_XML_KEY"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("YANDEX_API_KEY", "apikey")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1gfolder")
    called = {}

    def classic(q, auth, mr):
        called["classic_auth"] = auth
        return ["https://x.ru"]

    def cloud(q, *, max_results=20):
        called["cloud"] = True
        return []

    monkeypatch.setattr(search_mod, "_yandex_classic", classic)
    monkeypatch.setattr(search_mod, "search_yandex_cloud", cloud)
    assert search_mod.search_yandex("q") == ["https://x.ru"]
    assert called["classic_auth"] == {"apikey": "apikey", "folderid": "b1gfolder"}
    assert "cloud" not in called  # cloud не понадобился


def test_yandex_dispatcher_falls_back_to_cloud(monkeypatch):
    """Если классический endpoint пуст — используется Cloud v2."""
    for v in ("YANDEX_API_KEY", "YANDEX_FOLDER_ID", "YANDEX_XML_USER", "YANDEX_XML_KEY"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("YANDEX_API_KEY", "apikey")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "b1gfolder")

    monkeypatch.setattr(search_mod, "_yandex_classic", lambda q, auth, mr: [])
    monkeypatch.setattr(search_mod, "search_yandex_cloud",
                        lambda q, *, max_results=20: ["https://cloud.ru"])
    assert search_mod.search_yandex("q") == ["https://cloud.ru"]


def test_search_many_round_robin_dedupe(monkeypatch):
    def fake_search(query, *, provider, max_results=20, cache=None):
        data = {
            "yandex": ["https://a.ru", "https://b.ru", "https://c.ru"],
            "google": ["https://b.ru", "https://d.ru"],  # b.ru — дубль
        }
        return data[provider]

    monkeypatch.setattr(search_mod, "search", fake_search)
    merged = search_mod.search_many("q", providers=["yandex", "google"], max_results=20)
    # round-robin: yandex[0], google[0]=b, yandex[1]=b(дубль,скип), google[1]=d, yandex[2]=c
    assert merged == ["https://a.ru", "https://b.ru", "https://d.ru", "https://c.ru"]
