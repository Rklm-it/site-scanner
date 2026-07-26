"""Извлечение контактных данных со страницы."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .models import Contacts

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Российские и международные телефоны в свободной форме
PHONE_RE = re.compile(
    r"(?:\+7|7|8)[\s\-()]*\d{3}[\s\-()]*\d{3}[\s\-()]*\d{2}[\s\-()]*\d{2}"
)

INN_RE = re.compile(r"\bИНН[\s:]*?(\d{10}|\d{12})\b", re.I)
OGRN_RE = re.compile(r"\bОГРН(?:ИП)?[\s:]*?(\d{13}|\d{15})\b", re.I)

SOCIAL_HOSTS = {
    "vk.com": "VK",
    "t.me": "Telegram",
    "instagram.com": "Instagram",
    "facebook.com": "Facebook",
    "youtube.com": "YouTube",
    "wa.me": "WhatsApp",
    "api.whatsapp.com": "WhatsApp",
    "ok.ru": "OK",
    "wa.clck.bar": "WhatsApp",
}

# Мусорные адреса, которые не нужны как лид-контакт
JUNK_EMAIL_HINTS = ("example.com", "sentry.io", "wixpress.com", "@2x", ".png", ".jpg", ".webp")


def _clean_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    if len(digits) == 11 and digits[0] == "7":
        return f"+7 {digits[1:4]} {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
    return raw.strip()


def extract(html: str, *, base_url: str, title: str | None = None) -> Contacts:
    """Тянет со страницы email, телефоны, соцсети, ИНН/ОГРН и компанию."""
    soup = BeautifulSoup(html or "", "lxml")
    contacts = Contacts()

    # Email: из mailto и из текста
    emails: list[str] = []
    for a in soup.select('a[href^="mailto:"]'):
        addr = a["href"][len("mailto:"):].split("?")[0].strip()
        if addr:
            emails.append(addr)
    emails += EMAIL_RE.findall(html or "")
    contacts.emails = [
        e for e in dict.fromkeys(e.strip().rstrip(".") for e in emails)
        if not any(j in e.lower() for j in JUNK_EMAIL_HINTS)
    ][:5]

    # Телефоны: из tel: и из текста
    phones: list[str] = []
    for a in soup.select('a[href^="tel:"]'):
        phones.append(a["href"][len("tel:"):])
    phones += PHONE_RE.findall(html or "")
    cleaned = dict.fromkeys(_clean_phone(p) for p in phones)
    contacts.phones = [p for p in cleaned if p][:5]

    # Соцсети
    socials: list[str] = []
    for a in soup.find_all("a", href=True):
        host = urlparse(urljoin(base_url, a["href"])).netloc.lower().lstrip("www.")
        for known, _label in SOCIAL_HOSTS.items():
            if host.endswith(known):
                socials.append(urljoin(base_url, a["href"]).split("?")[0])
                break
    contacts.socials = list(dict.fromkeys(socials))[:8]

    # ИНН / ОГРН
    inn = INN_RE.search(html or "")
    if inn:
        contacts.inn = inn.group(1)
    ogrn = OGRN_RE.search(html or "")
    if ogrn:
        contacts.ogrn = ogrn.group(1)

    # Название компании: og:site_name -> title -> h1
    og_name = soup.find("meta", attrs={"property": "og:site_name"})
    if og_name and og_name.get("content"):
        contacts.company = og_name["content"].strip()
    elif title:
        contacts.company = title.split("|")[0].split("—")[0].strip()[:120] or None

    # Ссылка на страницу контактов
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True).lower()
        href = a["href"].lower()
        if "контакт" in text or "contact" in href or "/kontakt" in href:
            contacts.contact_page = urljoin(base_url, a["href"])
            break

    return contacts
