"""Тесты выгрузки сайта: обход, отсев мусора, лимиты, архив.

Сеть не трогаем — поднимаем крошечный сайт на локальном http.server. Так же,
как и в остальных тестах: песочница не пускает к российским доменам, а
проверять поведение надо на чём-то, что ведёт себя как настоящий сервер
(редиректы, content-type, битые ссылки).
"""

from __future__ import annotations

import http.server
import json
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
        <img src="/images/dom.jpg">
        <img src="data:image/gif;base64,R0lGOD" data-src="/images/lenivaya.jpg">
        <picture><source srcset="/images/shirokaya.webp 2x, /images/uzkaya.webp 1x"></picture>
        <div style="background-image: url('/images/fon-sekcii.png')"></div>
        <img src="https://st.chuzhoy-cdn.example/foto.jpg">
        <img src="/thumb.php?id=7">
        <img src="http://VNESHNIY_HOST/images/s-konstruktora.jpg#size_594x376">
        </body></html>""",
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
        if path in ("/images/dom.jpg", "/images/fon.png", "/images/lenivaya.jpg",
                    "/images/shirokaya.webp", "/images/uzkaya.webp",
                    "/images/fon-sekcii.png"):
            return self._send(b"\xff\xd8\xff" + b"0" * 200, "image/jpeg")
        if path == "/prays.pdf":
            return self._send(b"%PDF-1.4" + b"0" * 500, "application/pdf")
        if path == "/robots.txt":
            return self._send(b"User-agent: *\nDisallow: /administrator/\n", "text/plain")
        if path == "/sitemap.xml":
            host = self.headers.get("Host", "")
            return self._send(SITEMAP.replace(b"SITE", host.encode()), "application/xml")
        if path == "/images/s-konstruktora.jpg":
            return self._send(b"\xff\xd8\xff" + b"0" * 300, "image/jpeg")
        if path in PAGES:
            # Тот же сервер под другим именем хоста — так выглядит CDN
            # конструктора: страницы на домене клиента, картинки на чужом.
            port = self.headers.get("Host", "").split(":")[-1]
            body = PAGES[path].replace("VNESHNIY_HOST", f"localhost:{port}")
            # Кириллица в windows-1251 и без charset в заголовке — так отдаёт
            # добрая половина старых сайтов рунета.
            return self._send(body.encode("windows-1251"), "text/html")
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


def test_lenivye_kartinki_nahodyatsya(site, tmp_path):
    """Картинка в `src` — уже редкость: ленивая загрузка держит адрес в
    `data-src`, ретина в `srcset`, фон секции в атрибуте `style`. Пока
    смотрели только `src`, выгрузка мебельного сайта приезжала с нулём
    файлов, то есть без портфолио, ради которого её и делают.
    """
    _run(site, tmp_path / "d")
    files = {p.relative_to(tmp_path / "d").as_posix()
             for p in (tmp_path / "d").rglob("*") if p.is_file()}
    assert "images/lenivaya.jpg" in files        # data-src
    assert "images/shirokaya.webp" in files      # srcset у <source>
    assert "images/uzkaya.webp" in files
    assert "images/fon-sekcii.png" in files      # фон в атрибуте style


def test_pochemu_kartinok_net_vidno_iz_vygruzki(site, tmp_path):
    """Ноль картинок в архиве — самая частая жалоба, и причину выясняли
    запросами к живому сайту. Теперь отказы посчитаны и лежат в манифесте:
    видно и чужой хост, и картинку, которую отдаёт скрипт."""
    stats = _run(site, tmp_path / "d", external_images=False)
    assert stats.asset_refs >= 6
    prichiny = stats.asset_skipped
    assert any(k.startswith("чужой хост st.chuzhoy-cdn.example") for k in prichiny)
    assert any("без расширения" in k for k in prichiny)      # /thumb.php?id=7
    manifest = json.loads((tmp_path / "d" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["asset_skipped"] == prichiny


def test_kartinki_s_cdn_konstruktora_zabirayutsya(site, tmp_path):
    """Сайт на конструкторе держит фотографии на чужом хосте.

    У mebel-ryazane.ru все 23 тысячи адресов картинок вели на
    media.lpgenerator.ru, и выгрузка приезжала с нулём файлов при 88
    скачанных страницах. Для обхода это чужой хост, для клиента — его
    собственное портфолио, ради которого выгрузка и делается.
    """
    stats = _run(site, tmp_path / "d")
    nashli = list((tmp_path / "d" / "_vneshnie").rglob("s-konstruktora.jpg"))
    assert nashli, "картинка с чужого хоста не скачана"
    assert stats.assets_external >= 1
    # Стили и скрипты с чужих хостов по-прежнему мимо: чужое оформление в
    # разборе не нужно, а архив раздувает.
    assert not list((tmp_path / "d" / "_vneshnie").rglob("*.js"))


def test_chuzhie_kartinki_otklyuchaemy(site, tmp_path):
    stats = _run(site, tmp_path / "d", external_images=False)
    assert stats.assets_external == 0
    assert not (tmp_path / "d" / "_vneshnie").exists()


def test_robots_uvazhaetsya(site, tmp_path):
    _run(site, tmp_path / "d", respect_robots=True)
    assert not (tmp_path / "d" / "administrator").exists()


def test_limit_stranic_ostanavlivaet(site, tmp_path):
    stats = _run(site, tmp_path / "d", max_pages=2)
    assert stats.pages == 2
    assert stats.stopped_by == "limit"
    # Сколько именно не добрали — иначе «выгрузка неполная» выясняется через
    # неделю, когда сайт уже разобран не весь.
    assert stats.pages_left > 0


def test_potolok_obyoma_ostanavlivaet_i_nazyvaetsya(site, tmp_path):
    """Упёрлись в объём — это должно быть видно, а не выглядеть успехом.

    Сайт на конструкторе держит фотографии на чужом CDN, и там их тысячи:
    у mebel-ryazane.ru 3005 картинок, которые в прежние зашитые 200 МБ не
    влезают. Обход обязан назвать причину остановки и сказать, сколько не
    добрано, иначе половина портфолио теряется молча.
    """
    stats = mirror.run(site, tmp_path / "d", scheme="http", respect_robots=False,
                       per_host_delay=0, max_total_bytes=300)
    assert stats.stopped_by == "bytes"
    assert stats.pages_left + stats.assets_left > 0


def test_mesto_na_diske_ostanavlivaet_vygruzku(site, tmp_path):
    """Диск кончился — обход обязан остановиться сам и назвать причину.

    Выгрузка лежит на том же томе, что база лидов и ключи. На сервере
    владельца под /data оставалось 533 МБ, а сайту на конструкторе нужен
    гигабайт: без этой границы выгрузка чужих фотографий останавливает весь
    инструмент, и чинится это руками на сервере.
    """
    stats = mirror.run(site, tmp_path / "d", scheme="http", respect_robots=False,
                       per_host_delay=0, min_free_bytes=10 ** 15)
    assert stats.stopped_by == "disk"


def test_kartinkam_ostayotsya_vremya_kogda_stranicy_ne_uspeli(site, tmp_path):
    """Картинки качаются последними и раньше оставались без бюджета совсем.

    На papinalavka.ru выгрузка выглядела успешной — 500 страниц, — а картинок
    приехало 76 из 850: страницы по 0,7 секунды съели семь минут целиком.
    Теперь доля времени под картинки удержана заранее.
    """
    stats = mirror.run(site, tmp_path / "d", scheme="http", respect_robots=False,
                       per_host_delay=0.2, time_budget=1.0)
    assert stats.pages_left > 0        # страницам времени не хватило
    assert stats.assets >= 1           # но картинки всё равно приехали
    assert stats.stopped_by == "deadline"


def test_ostatok_vremeni_vozvrashaetsya_stranicam(site, tmp_path):
    """Доля под картинки не должна сгорать на сайте, где картинок мало.

    Страницам отдано всего 20% бюджета — за это время сайт не обойти. Но
    картинки заканчиваются быстро, и остаток возвращается страницам: выгрузка
    приезжает полной, а не обрезанной по искусственной границе фаз.
    """
    stats = mirror.run(site, tmp_path / "d", scheme="http", respect_robots=False,
                       per_host_delay=0.2, time_budget=3.0, assets_share=0.8)
    assert stats.pages_left == 0
    assert stats.stopped_by == "done"


def test_pack_ne_derzhit_dve_kopii(tmp_path, monkeypatch):
    """В пике на диске должна лежать одна копия выгрузки, а не две.

    Пока файлы удалялись после упаковки, выгрузке на 212 МБ требовалось 424 МБ
    свободных — на сервере владельца столько не набиралось при 537 МБ на всё.
    Считаем, сколько исходных файлов ещё живо в момент каждой записи в архив:
    при упаковке «по мере удаления» это число убывает.
    """
    src = tmp_path / "work"
    (src / "vnutri").mkdir(parents=True)
    for i in range(5):
        (src / "vnutri" / f"{i}.jpg").write_bytes(b"\xff\xd8\xff" + bytes(1000))

    zhivyh = []
    nastoyashchiy = zipfile.ZipFile.write

    def schitat(self, filename, arcname=None, **kw):
        zhivyh.append(sum(1 for p in src.rglob("*") if p.is_file()))
        return nastoyashchiy(self, filename, arcname, **kw)

    monkeypatch.setattr(zipfile.ZipFile, "write", schitat)
    mirror.pack(src, tmp_path / "arhiv.zip")

    assert zhivyh == [5, 4, 3, 2, 1]      # каждый файл уходит сразу после записи
    assert not src.exists()               # рабочая папка убрана целиком
    with zipfile.ZipFile(tmp_path / "arhiv.zip") as zf:
        assert len(zf.namelist()) == 5    # и при этом в архиве всё


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


class _OtkazHandler(http.server.BaseHTTPRequestHandler):
    """Сайт, закрытый защитой платформы: 503 со страницей проверки на всё.

    Так ведёт себя `rgz61.ru` на конструкторе «Пульс цен» — и с сервера, и с
    машины владельца выгрузка получает не сайт, а заглушку.
    """

    def log_message(self, *a):
        pass

    def do_GET(self):  # noqa: N802
        body = ("<html><head><meta charset='utf-8'>"
                "<title>Проверка безопасности</title></head><body>стоп</body></html>"
                ).encode("utf-8")
        self.send_response(503)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_HEAD = do_GET


@pytest.fixture()
def otkaz_site():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _OtkazHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_statusy_otvetov_popadayut_v_statistiku(site, tmp_path):
    """Счётчик ответов — единственное, что отличает медленный сайт от
    закрытого: «страниц 0» одинаково выглядит в обоих случаях."""
    stats = _run(site, tmp_path / "d")
    assert stats.statuses[200] >= stats.pages


def test_progress_soobshchaetsya_i_pri_otkaze(otkaz_site, tmp_path):
    """Выгрузка сайта, отвечающего одними отказами, десять минут выглядела
    зависшей: on_progress звали только после удачно скачанной страницы, и в
    интерфейсе висело «страниц 0, файлов 0» без единого движения."""
    seen: list[tuple[int, dict]] = []
    stats = _run(otkaz_site, tmp_path / "d", use_sitemap=False,
                 on_progress=lambda st: seen.append((st.pages, dict(st.statuses))))

    assert stats.pages == 0
    assert seen, "о неудачных ответах прогресс тоже обязан сообщать"
    assert stats.statuses == {503: 1}


def test_shema_beryotsya_ta_chto_otvetila(otkaz_site):
    """Сайт за защитой отвечает 503 по http и не слушает https. Раньше в
    таком случае корень откатывался на https, и выгрузка падала с SSL-ошибкой
    вместо честного «сайт отвечает отказом» — причина видна совсем не та."""
    import requests

    root = mirror._pick_root(otkaz_site, requests.Session(), timeout=5)
    assert root.startswith("http://")
