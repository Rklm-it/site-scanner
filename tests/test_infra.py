"""Тесты кэша, детекта кодировки и вежливости."""

from scanner.cache import Cache
from scanner.fetcher import detect_encoding, FetchResult
from scanner.politeness import Politeness


def test_detect_encoding_from_header():
    assert detect_encoding(b"<html></html>", {"content-type": "text/html; charset=windows-1251"}) == "windows-1251"


def test_detect_encoding_from_meta():
    raw = "<html><head><meta charset='utf-8'></head></html>".encode()
    assert detect_encoding(raw, {}) == "utf-8"


def test_detect_encoding_cp1251_autodetect():
    # Кириллица в cp1251 без объявления кодировки — должен распознаться как 1251-семейство
    raw = "Стоматология Казань, добро пожаловать".encode("cp1251")
    enc = detect_encoding(raw, {}).lower()
    assert "1251" in enc or "windows" in enc or "cp" in enc


def test_cache_search_roundtrip(tmp_path):
    c = Cache(str(tmp_path / "c.sqlite"))
    assert c.get_search("q", "yandex") is None
    c.set_search("q", "yandex", ["https://a.ru", "https://b.ru"])
    assert c.get_search("q", "yandex") == ["https://a.ru", "https://b.ru"]
    c.close()


def test_cache_search_ttl(tmp_path):
    c = Cache(str(tmp_path / "c.sqlite"), search_ttl=0)
    c.set_search("q", "yandex", ["https://a.ru"])
    assert c.get_search("q", "yandex") is None  # ttl=0 → всегда просрочено
    c.close()


def test_cache_seen(tmp_path):
    c = Cache(str(tmp_path / "c.sqlite"))
    assert not c.is_seen("a.ru")
    c.mark_seen("a.ru", 50)
    assert c.is_seen("a.ru")
    c.close()


def test_cache_pages_disabled_by_default(tmp_path):
    c = Cache(str(tmp_path / "c.sqlite"))
    res = FetchResult(url="https://a.ru", status=200, html="<html>", headers={})
    c.set_page(res)
    assert c.get_page("https://a.ru") is None  # cache_pages=False
    c.close()


def test_cache_pages_enabled(tmp_path):
    c = Cache(str(tmp_path / "c.sqlite"), cache_pages=True)
    res = FetchResult(url="https://a.ru", status=200, final_url="https://a.ru",
                      html="<html>привет</html>", headers={"server": "nginx"}, https=True)
    c.set_page(res)
    got = c.get_page("https://a.ru")
    assert got is not None and got.html == "<html>привет</html>" and got.https
    c.close()


def test_politeness_robots_disabled_allows_all():
    p = Politeness(respect_robots=False)
    assert p.allowed("https://any-site.ru/whatever")
