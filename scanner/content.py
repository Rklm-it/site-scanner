"""Содержимое старого сайта: разделы, заголовки, описание, картинки.

Зачем: прототип нового сайта должен показывать РЕАЛЬНЫЕ услуги клиента, а не
придуманные «типовые под нишу». Мы и так скачиваем страницу целиком ради
эвристик устаревания — грех не забрать оттуда то, из чего собирается бриф:
меню (это и есть перечень услуг), заголовки, описание и фотографии.

Клиент на звонке видит своё: свои разделы, свои снимки. Это принципиально
другой разговор, чем «вот шаблон, представьте на его месте себя».
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

# Пункты меню, которые не являются услугами — в бриф не нужны.
_MENU_STOP = {
    "главная", "home", "контакты", "contacts", "о нас", "о компании", "about",
    "новости", "блог", "blog", "корзина", "cart", "вход", "войти", "login",
    "регистрация", "поиск", "search", "карта сайта", "наверх", "меню",
    "политика конфиденциальности", "帮助",
}

# Служебная графика: логотипы, иконки, счётчики, спрайты — не иллюстрации.
_IMG_STOP = re.compile(
    r"(logo|icon|sprite|favicon|counter|pixel|banner_?ad|placeholder|spacer|blank|1x1)",
    re.I)
_IMG_EXT = re.compile(r"\.(jpe?g|png|webp|avif)(\?|$)", re.I)


@dataclass
class SiteContent:
    """Что удалось вытащить со старого сайта для брифа."""

    description: str | None = None
    menu: list[str] = field(default_factory=list)       # разделы = услуги
    headings: list[str] = field(default_factory=list)   # h1/h2
    images: list[str] = field(default_factory=list)     # абсолютные URL

    @property
    def is_empty(self) -> bool:
        return not (self.description or self.menu or self.headings or self.images)


def _clean(value: str, limit: int) -> str:
    return re.sub(r"\s+", " ", value or "").strip()[:limit]


def extract(html: str, *, base_url: str) -> SiteContent:
    """Разбирает страницу на составляющие будущего брифа."""
    soup = BeautifulSoup(html or "", "lxml")
    out = SiteContent()

    meta = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    if meta and meta.get("content"):
        out.description = _clean(meta["content"], 300) or None

    # Меню: сначала пробуем настоящую навигацию, иначе — любые ссылки в шапке.
    seen: set[str] = set()
    for a in soup.select("nav a, header a, .menu a, .nav a, ul.menu a"):
        text = _clean(a.get_text(" ", strip=True), 60)
        low = text.lower()
        if not (2 < len(text) <= 60) or low in _MENU_STOP or low in seen:
            continue
        if text.startswith(("+7", "8 ")) or "@" in text:      # это контакты, не раздел
            continue
        seen.add(low)
        out.menu.append(text)
        if len(out.menu) >= 14:
            break

    for tag in soup.find_all(["h1", "h2"]):
        text = _clean(tag.get_text(" ", strip=True), 120)
        if 3 < len(text) <= 120 and text.lower() not in seen:
            seen.add(text.lower())
            out.headings.append(text)
        if len(out.headings) >= 8:
            break

    # Картинки: og:image приоритетнее — её владелец выбирал сам.
    urls: list[str] = []
    og = soup.find("meta", attrs={"property": "og:image"})
    if og and og.get("content"):
        urls.append(urljoin(base_url, og["content"]))
    for img in soup.find_all("img", src=True):
        src = img["src"].strip()
        if not src or src.startswith("data:") or _IMG_STOP.search(src):
            continue
        full = urljoin(base_url, src)
        if not _IMG_EXT.search(urlparse(full).path):
            continue
        if full not in urls:
            urls.append(full)
        if len(urls) >= 8:
            break
    out.images = urls

    return out
