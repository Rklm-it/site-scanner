"""Тесты выгрузки сайта: обход, отсев мусора, лимиты, архив.

Сеть не трогаем — поднимаем крошечный сайт на локальном http.server. Так же,
как и в остальных тестах: песочница не пускает к российским доменам, а
проверять поведение надо на чём-то, что ведёт себя как настоящий сервер
(редиректы, content-type, битые ссылки).
"""

from __future__ import annotations

import http.server
import threading
import zipfile
from functools import partial
from pathlib import Path

import pytest

from scanner import mirror

# Сайт-образец повторяет то, на чём выгрузка спотыкалась в бою: страница в
# windows-1251, RSS-лента по «?format=feed», тяжёлый PDF, ссылка на чужой
# домен и фоновая картинка, подключённая только из CSS.
PAGES = {
    "/": """<html><head><title>Главная</title>
        <link rel="stylesheet" href="/css/style.css"></head>
        <body><h1>Проекты домов</h1>
        <a href="/uslugi">Услуги</a>
        <a href="/katalog/dom-1">Дом 1</a>
        <a href="/?format=feed&type=rss">RSS</a>
        <a href="/katalog?start=60">Страница 2</a>
        <a href="/uslugi?sort=name&dir=asc">Сортировка</a>
        <a href="/prays.pdf">Прайс</a>
        <a href="https://chужой.example/x">Партнёр</a>
        <a href="/administrator/index.php">Админка</a>
        <img src="/images/dom.jpg"></body></html>""",
    "/uslugi": "<html><head><title>Услуги</title></head><body><h1>Услуги</h1>"
               "<a href='/katalog/dom-2'>Дом 2</a></body></html>",
    "/katalog/dom-1": "<html><head><title>Дом 1</title></head><body>Дом 1</body></html>",
    "/katalog/dom-2": "<html><head><title>Дом 2</title></head><body>Дом 2</body></html>",
    # вторая страница каталога: карточка К-3 больше ниоткуда не доступна
    "/katalog": "<html><head><title>Каталог</title></head><body>"
                "<a href='/katalog/dom-3'>Дом 3</a></body></html>",
    "/katalog/dom-3": "<html><head><title>Дом 3</title></head><body>Дом 3</body></html>",
    "/administrator/index.php": "<html><title>Админка</title><body>секрет</body></html>",
    # Страница, на которую нет ни одной ссылки — только в карте сайта
    "/tajnaya": "<html><head><title>Тайная</title></head><body>Тайная</body></html>",
}
SITEMAP = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>http://SITE/</loc></url>
  <url><loc>http://SITE/tajnaya</loc></url>
  <url><loc>http://SITE/prays.pdf</loc></url>
</urlset>"""
CSS = b"body { background: url('/images/fon.png') repeat; }"


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):  # тишина в выводе тестов
        pass

    def do_GET(self):  # noqa: N802
        path = self.path.split("?")[0]
        if self.path.startswith("/?format=feed"):
            return self._send(b"<rss/>", "application/rss+xml")
        if path == "/css/style.css":
            return self._send(CSS, "text/css")
        if path in ("/images/dom.jpg", "/images/fon.png"):
            return self._send(b"\xff\xd8\xff" + b"0" * 200, "image/jpeg")
        if path == "/prays.pdf":
            return self._send(b"%PDF-1.4" + b"0" * 500, "application/pdf")
        if path == "/robots.txt":
            return self._send(b"User-agent: *\nDisallow: /administrator/\n", "text/plain")
        if path == "/sitemap.xml":
            host = self.headers.get("Host", "")
            return self._send(SITEMAP.replace(b"SITE", host.encode()), "application/xml")
        if path in PAGES:
            # Кириллица в windows-1251 и без charset в заголовке — так отдаёт
            # добрая половина старых сайтов рунета.
            return self._send(PAGES[path].encode("windows-1251"), "text/html")
        self.send_error(404)

    def _send(self, body: bytes, ctype: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture()
def site():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _run(site: str, dest: Path, **kw) -> mirror.MirrorStats:
    """Локальный сервер без TLS — фиксируем схему, иначе выгрузка сначала
    впустую постучится по https."""
    kw.setdefault("respect_robots", False)
    return mirror.run(site, dest, scheme="http", per_host_delay=0, **kw)


def test_obhod_sobiraet_stranicy_i_kartinki(site, tmp_path):
    stats = _run(site, tmp_path / "d")

    files = {p.relative_to(tmp_path / "d").as_posix()
             for p in (tmp_path / "d").rglob("*") if p.is_file()}
    assert "index.html" in files
    assert "uslugi.html" in files            # без расширения — доклеили .html
    assert "katalog/dom-1.html" in files
    assert "katalog/dom-2.html" in files     # нашли на глубине 2
    assert stats.pages >= 4


def test_kodirovka_privoditsya_k_utf8(site, tmp_path):
    _run(site, tmp_path / "d")
    text = (tmp_path / "d" / "index.html").read_text(encoding="utf-8")
    # Ради этого всё и затевалось: windows-1251 в репозитории нечитаем
    assert "Проекты домов" in text


def test_korotkie_stranicy_ne_uezzhayut_v_krakozyabry(site, tmp_path):
    """Автодетектор кодировки врёт на коротких страницах: карточка из двух
    строк в windows-1251 определялась как японская, и в разбор попадало
    «ﾄ黑 1» вместо «Дом 1». Внутренние страницы обязаны читаться так же
    надёжно, как главная."""
    stats = _run(site, tmp_path / "d")
    text = (tmp_path / "d" / "katalog" / "dom-1.html").read_text(encoding="utf-8")
    assert "Дом 1" in text
    # заодно и карта сайта: по ней потом разбирается структура
    titles = {p["title"] for p in stats.pages_index}
    assert {"Дом 1", "Дом 2", "Услуги"} <= titles


@pytest.mark.parametrize("enc,ctype", [
    ("utf-8", "text/html"),
    ("windows-1251", "text/html"),
    ("windows-1251", "text/html; charset=windows-1251"),
    ("utf-8", "text/html; charset=utf-8"),
])
def test_dekoder_uznayot_kodirovku(enc, ctype):
    raw = "<html><title>Дом 1</title></html>".encode(enc)
    text, _ = mirror._decode_page(raw, ctype, learned=None)
    assert "Дом 1" in text


def test_dekoder_vryot_zayavlennoy_kodirovke_ne_verit():
    """Старые сайты объявляют одно, а отдают другое. Если по заявленной
    кодировке текст не разбирается — не молчим, а идём дальше по списку."""
    raw = "<html><title>Дом 1</title></html>".encode("windows-1251")
    text, used = mirror._decode_page(raw, "text/html; charset=utf-8", learned=None)
    assert "Дом 1" in text and used == "windows-1251"


def test_paginaciya_kataloga_ne_teryaetsya(site, tmp_path):
    """Адреса с запросом мы глушим ради RSS-лент, но пагинация — исключение:
    у projekt-doma.ru за `?start=60` лежала половина каталога, и без неё
    выгрузка молча возвращала неполный список проектов."""
    _run(site, tmp_path / "d")
    files = {p.relative_to(tmp_path / "d").as_posix()
             for p in (tmp_path / "d").rglob("*") if p.is_file()}
    assert "katalog~start_60.html" in files      # сама страница пагинации
    assert "katalog/dom-3.html" in files         # и карточка, доступная только с неё
    assert not any("sort" in f for f in files)   # а сортировка по-прежнему мимо


def test_karta_sajta_nahodit_nesvyazannye_stranicy(site, tmp_path):
    """В меню попадает не всё: у блогов и каталогов часть страниц не
    прилинкована ниоткуда. Карта сайта перечисляет их явно — без неё выгрузка
    молча возвращает неполный сайт, а понять это по числу страниц нельзя."""
    stats = _run(site, tmp_path / "d")
    files = {p.relative_to(tmp_path / "d").as_posix()
             for p in (tmp_path / "d").rglob("*") if p.is_file()}
    assert "tajnaya.html" in files                       # только из карты
    assert "prays.pdf" not in files                      # тяжёлое отсекается и здесь
    assert any(p["title"] == "Тайная" for p in stats.pages_index)


def test_karta_sajta_otklyuchaema(site, tmp_path):
    stats = _run(site, tmp_path / "d", use_sitemap=False)
    assert all(p["title"] != "Тайная" for p in stats.pages_index)


def test_musor_ne_kachaetsya(site, tmp_path):
    _run(site, tmp_path / "d")
    files = {p.name for p in (tmp_path / "d").rglob("*") if p.is_file()}
    assert not any("format=feed" in f for f in files)   # RSS-ленты
    assert "prays.pdf" not in files                     # тяжёлое
    assert not (tmp_path / "d" / "administrator").exists()  # служебка CMS


def test_chuzhoy_domen_ne_trogaem(site, tmp_path):
    stats = _run(site, tmp_path / "d")
    assert all("example" not in p["url"] for p in stats.pages_index)


def test_kartinka_iz_css_nahoditsya(site, tmp_path):
    _run(site, tmp_path / "d")
    files = {p.as_posix() for p in
             (p.relative_to(tmp_path / "d") for p in (tmp_path / "d").rglob("*") if p.is_file())}
    assert "css/style.css" in files
    assert "images/fon.png" in files    # подключена только фоном в CSS


def test_robots_uvazhaetsya(site, tmp_path):
    _run(site, tmp_path / "d", respect_robots=True)
    assert not (tmp_path / "d" / "administrator").exists()


def test_limit_stranic_ostanavlivaet(site, tmp_path):
    stats = _run(site, tmp_path / "d", max_pages=2)
    assert stats.pages == 2
    assert stats.stopped_by == "limit"


def test_manifest_i_arhiv(site, tmp_path):
    dest = tmp_path / "d"
    _run(site, dest)
    assert (dest / "manifest.json").exists()

    archive = tmp_path / "out.zip"
    size = mirror.pack(dest, archive)
    assert size > 0
    assert not dest.exists()            # распакованное убрали с тома
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
    assert "index.html" in names and "manifest.json" in names


@pytest.mark.parametrize("url,expected", [
    ("https://x.ru/", "index.html"),
    ("https://x.ru/uslugi", "uslugi.html"),
    ("https://x.ru/a/b/", "a/b.html"),
    ("https://x.ru/images/foto.jpg", "images/foto.jpg"),
    # Пробел в имени файла: на сайте «410 1.jpg», в адресе «410%201.jpg».
    # Без раскодирования получалось «410_201.jpg» — имя читается как число.
    ("https://x.ru/images/410%201.jpg", "images/410_1.jpg"),
    ("https://x.ru/%D0%B4%D0%BE%D0%BC.html", "дом.html"),
    ("https://x.ru/style.css?v=3", "style.css"),
    # Пагинация каталога: вторая страница не должна перезаписать первую
    ("https://x.ru/katalog?start=60", "katalog~start_60.html"),
    ("https://x.ru/katalog.html?start=60", "katalog~start_60.html"),
    # «..» в чужой ссылке не должна уводить запись выше папки выгрузки
    ("https://x.ru/../../etc/passwd", "etc/passwd.html"),
])
def test_put_v_arhive(url, expected):
    assert mirror._local_path(url) == expected


def test_domen_ochischaetsya():
    """Из формы приходит и «https://site.ru/», и «site.ru» — оба варианта
    должны дать один и тот же обход."""
    assert mirror._same_site("https://www.site.ru/a", "site.ru")
    assert mirror._same_site("https://site.ru/a", "www.site.ru")
    assert not mirror._same_site("https://shop.site.ru/a", "site.ru")
    assert not mirror._same_site("https://site.ru.evil.com/a", "site.ru")
