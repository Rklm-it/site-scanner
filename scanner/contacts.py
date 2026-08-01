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

# В подвалах реквизиты пишут слитными парами: «ИНН/КПП 7707083893/770701001»,
# «ОГРН/ИНН 1027700132195 / 7707083893», «ИНН — 7707083893», «ИНН №7707083893».
# Старый шаблон допускал между меткой и числом только пробелы, двоеточие и слэш,
# поэтому все эти варианты пролетали мимо — а без ИНН не узнать оборот.
# Теперь между меткой и числом допускается до 12 НЕцифровых символов (буквы
# «КПП», тире, №, скобки), и необязательно — один «чужой» номер из соседней
# метки в парной записи. Длины ограничены сверху: откат по большой странице
# должен оставаться линейным. Найденное всё равно проходит проверку
# контрольной суммы в validate_inn/validate_ogrn — мусор не пройдёт.
INN_RE = re.compile(
    r"\bИНН\b(?:[^0-9]{0,12}\d{13,15})?[^0-9]{0,12}(\d{10}|\d{12})(?!\d)", re.I)
OGRN_RE = re.compile(
    r"\bОГРН(?:ИП)?\b(?:[^0-9]{0,12}\d{10,12})?[^0-9]{0,12}(\d{13}|\d{15})(?!\d)", re.I)

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

    # Юридическое название из текста страницы — им ищем компанию в реестрах.
    contacts.legal_name = find_legal_name(text)

    # Ссылки на страницы контактов/реквизитов, в порядке полезности
    pages = find_contact_links(soup, base_url)
    contacts.contact_page = pages[0] if pages else None
    contacts.extra_pages = pages[1:]

    return contacts


# Организационно-правовые формы. По заголовку страницы («Салон красоты "Крокус"
# в Ростове-на-Дону.») реестр компанию не находит, а по «ООО «Крокус»» —
# находит. Поэтому юрлицо ищем в видимом тексте отдельно от заголовка.
_OPF = "ООО|ЗАО|ОАО|ПАО|АО|ГУП|МУП|ФГУП|АНО|НКО|ТСЖ|КФХ"
# Между формой и названием часто стоит короткая аббревиатура-приставка:
# «ООО ПКФ "НОВЫЙ КОЛОС"», «ГУП РО "Фармацевтический центр"», «ЗАО НПО ...».
# Без неё в реестр уходило обрубленное «ООО ПКФ».
LEGAL_RE = re.compile(
    rf"\b({_OPF})\s*(\w{{2,5}}\s+)?[«\"'“]([^»\"'”<>\n]{{2,80}})[»\"'”]", re.I)
# То же без кавычек: «ООО Ромашка», «ГУП РО Фармацевтический центр».
# Продолжать название могут слова с большой буквы или типовые «хвосты» вроде
# «центр»/«завод» — иначе в имя утягивался сказуемый глагол из предложения
# («ЗАО Ростовский Завод работает с 1998»).
_NAME_TAIL = ("центр|завод|дом|комбинат|компания|группа|фабрика|банк|холдинг"
              "|сервис|строй|торг|бюро|агентство|студия|клиника|аптека")
LEGAL_BARE_RE = re.compile(
    rf"\b({_OPF})\s+((?:[А-ЯЁ][А-Яа-яЁё\-]+|[А-ЯЁ]{{2,5}})"
    rf"(?:\s+(?:[А-ЯЁ][А-Яа-яЁё\-]+|(?:{_NAME_TAIL})\b)){{0,4}})")
IP_NAME_RE = re.compile(
    r"\bИП\s+([А-ЯЁ][а-яё\-]{1,30}\s+[А-ЯЁ][а-яё]{1,30}(?:\s+[А-ЯЁ][а-яё]{1,30})?)")


def find_legal_name(text: str) -> str | None:
    """Юридическое название компании из видимого текста страницы."""
    m = LEGAL_RE.search(text)
    if m:
        # Приставку берём только если это аббревиатура (ПКФ, РО, НПО), иначе
        # в название затесалось бы обычное слово из предложения.
        prefix = (m.group(2) or "").strip()
        prefix = f"{prefix} " if prefix.isupper() else ""
        return f'{m.group(1).upper()} {prefix}«{m.group(3).strip()}»'
    m = IP_NAME_RE.search(text)
    if m:
        return f"ИП {m.group(1).strip()}"
    m = LEGAL_BARE_RE.search(text)
    if m:
        return f"{m.group(1).upper()} {m.group(2).strip()}"
    return None


# Чем выше в списке — тем вероятнее на странице есть ИНН. «Реквизиты» бьют
# «контакты»: раньше бралась первая попавшаяся ссылка, и вместо реквизитов
# бот часто уходил на «О нас», где ИНН нет.
_LINK_HINTS = (
    (("реквизит", "requisite", "rekvizit"), 0),
    (("контакт", "contact", "kontakt"), 1),
    (("о компании", "о нас", "about"), 2),
)


def find_contact_links(soup: BeautifulSoup, base_url: str, limit: int = 3) -> list[str]:
    """Ссылки на контакты/реквизиты в порядке шанса найти там ИНН."""
    found: list[tuple[int, str]] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True).lower()
        href = a["href"].lower()
        rank = next((r for hints, r in _LINK_HINTS
                     if any(h in text for h in hints) or any(h in href for h in hints)), None)
        if rank is None:
            continue
        full = urljoin(base_url, a["href"])
        if urlparse(full).netloc != urlparse(base_url).netloc or full in seen:
            continue
        seen.add(full)
        found.append((rank, full))
    found.sort(key=lambda x: x[0])
    return [url for _, url in found[:limit]]


def find_contact_link(soup: BeautifulSoup, base_url: str) -> str | None:
    """Самая перспективная страница контактов/реквизитов (или None)."""
    links = find_contact_links(soup, base_url, limit=1)
    return links[0] if links else None
