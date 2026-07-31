"""Извлечение контактных данных со страницы."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .models import Contacts
from .validators import validate_inn, validate_ogrn

# Длины ограничены сверху НАМЕРЕННО. С открытыми «+» движок re на каждой
# неудачной позиции откатывался по всей длине совпадения, и на минифицированном
# JS или data:-картинке в пару мегабайт это вырождалось в квадрат: один такой
# сайт вешал скан на «пункте» намертво — а поскольку re не отпускает GIL,
# вместе со сканом замирал и веб-интерфейс. Пределы взяты из RFC 5321
# (локальная часть ≤64, домен ≤255) — реальные адреса не режем.
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]{1,64}@[a-zA-Z0-9.\-]{1,255}\.[a-zA-Z]{2,24}")

# Российские и международные телефоны в свободной форме (в т.ч. 8-800).
# Разделителей между группами цифр в живой вёрстке максимум 2-3 («+7 (999)»).
PHONE_RE = re.compile(
    r"(?:\+7|7|8)[\s\-()]{0,6}\d{3}[\s\-()]{0,6}\d{3}[\s\-()]{0,6}\d{2}[\s\-()]{0,6}\d{2}"
)

INN_RE = re.compile(r"\bИНН[\s:/]*?(\d{10}|\d{12})\b", re.I)
OGRN_RE = re.compile(r"\bОГРН(?:ИП)?[\s:/]*?(\d{13}|\d{15})\b", re.I)

SOCIAL_HOSTS = (
    "vk.com", "t.me", "instagram.com", "facebook.com", "youtube.com",
    "wa.me", "api.whatsapp.com", "ok.ru", "wa.clck.bar", "dzen.ru",
)

JUNK_EMAIL_HINTS = (
    "example.com", "sentry.io", "wixpress.com", "@2x", ".png", ".jpg", ".webp",
    ".gif", ".svg", ".woff", ".ttf", ".js", ".css", ".ico",
)

# Деобфускация email вида "info (at) site точка ru".
# ВАЖНО: срабатывает ТОЛЬКО на явных разделителях — скобках [( )] или пробелах
# вокруг «at»/«собака»/«точка». Иначе «at»/«dot» ловились бы внутри слов
# (loc**at**ion → loc@ion, **lat**in → l@in) и порождали мусорные адреса из JS.
_DEOBFUSCATE = [
    (re.compile(r"\s*[\[(]\s*(?:at|собака)\s*[\])]\s*", re.I), "@"),   # (at) [собака]
    (re.compile(r"\s+(?:собака)\s+", re.I), "@"),                       #  собака
    (re.compile(r"\s*[\[(]\s*(?:dot|точка)\s*[\])]\s*", re.I), "."),   # (dot) [точка]
    (re.compile(r"\s+(?:точка)\s+", re.I), "."),                        #  точка
]


def _clean_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    if len(digits) == 11 and digits[0] == "7":
        return f"+7 {digits[1:4]} {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
    return raw.strip()


def _deobfuscate(text: str) -> str:
    for pattern, repl in _DEOBFUSCATE:
        text = pattern.sub(repl, text)
    return text


def _first_valid(matches: list[str], validator) -> str | None:
    for m in matches:
        if validator(m):
            return m
    return None


def extract(html: str, *, base_url: str, title: str | None = None) -> Contacts:
    """Тянет со страницы email, телефоны, соцсети, ИНН/ОГРН и компанию."""
    soup = BeautifulSoup(html or "", "lxml")
    contacts = Contacts()
    raw = html or ""
    deobf = _deobfuscate(raw)

    # Email: из mailto и из текста (с учётом деобфускации)
    emails: list[str] = []
    for a in soup.select('a[href^="mailto:"]'):
        addr = a["href"][len("mailto:"):].split("?")[0].strip()
        if addr:
            emails.append(addr)
    emails += EMAIL_RE.findall(deobf)
    contacts.emails = [
        e for e in dict.fromkeys(e.strip().rstrip(".").lower() for e in emails)
        if not any(j in e for j in JUNK_EMAIL_HINTS)
    ][:8]

    # Телефоны: из tel: и из текста
    phones: list[str] = []
    for a in soup.select('a[href^="tel:"]'):
        phones.append(a["href"][len("tel:"):])
    phones += PHONE_RE.findall(raw)
    contacts.phones = [p for p in dict.fromkeys(_clean_phone(p) for p in phones) if p][:8]

    # Соцсети и мессенджеры
    socials: list[str] = []
    for a in soup.find_all("a", href=True):
        full = urljoin(base_url, a["href"])
        host = urlparse(full).netloc.lower().removeprefix("www.")
        if any(host == k or host.endswith("." + k) for k in SOCIAL_HOSTS):
            socials.append(full.split("?")[0])
    contacts.socials = list(dict.fromkeys(socials))[:10]

    # ИНН / ОГРН — по ВИДИМОМУ тексту, а не по сырому HTML. Иначе метку и число
    # в соседних тегах (<span>ИНН:</span> <span>7712345678</span>) разделяют
    # теги, и регэксп по HTML их не склеивает — ИНН терялся у большинства сайтов.
    text = soup.get_text(" ", strip=True)
    contacts.inn = _first_valid(INN_RE.findall(text), validate_inn)
    contacts.ogrn = _first_valid(OGRN_RE.findall(text), validate_ogrn)

    # Название компании: og:site_name -> title
    og_name = soup.find("meta", attrs={"property": "og:site_name"})
    if og_name and og_name.get("content"):
        contacts.company = og_name["content"].strip()
    elif title:
        contacts.company = title.split("|")[0].split("—")[0].strip()[:120] or None

    # Ссылка на страницу контактов
    contacts.contact_page = find_contact_link(soup, base_url)

    return contacts


_CONTACT_HINTS = ("контакт", "contact", "kontakt", "о нас", "about", "реквизит")


def find_contact_link(soup: BeautifulSoup, base_url: str) -> str | None:
    """Ищет ссылку на страницу контактов/реквизитов."""
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True).lower()
        href = a["href"].lower()
        if any(h in text for h in _CONTACT_HINTS) or any(h in href for h in ("contact", "kontakt")):
            full = urljoin(base_url, a["href"])
            if urlparse(full).netloc == urlparse(base_url).netloc:
                return full
    return None
