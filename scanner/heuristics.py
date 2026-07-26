"""Эвристики «устаревания» дизайна сайта.

Каждый сигнал добавляет баллы к ``outdated_score`` (0..100).
Чем выше итог — тем древнее сайт и тем «горячее» лид для редизайна.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

CURRENT_YEAR = datetime.date.today().year

# CMS/конструкторы и их «поколение». Старые генераторы — сильный сигнал.
CMS_PATTERNS: list[tuple[str, str]] = [
    (r"joomla!?\s*1\.", "Joomla 1.x (очень старая)"),
    (r"joomla!?\s*2\.", "Joomla 2.x (старая)"),
    (r"wordpress\s*[123]\.", "WordPress 1-3.x (старая)"),
    (r"drupal\s*[567]\b", "Drupal 5-7 (старый)"),
    (r"ucoz", "uCoz (конструктор)"),
    (r"frontpage", "MS FrontPage (реликт)"),
    (r"dreamweaver", "Dreamweaver (реликт)"),
    (r"1c-bitrix", "1С-Битрикс"),
    (r"joomla", "Joomla"),
    (r"wordpress", "WordPress"),
    (r"drupal", "Drupal"),
    (r"wix\.com", "Wix"),
    (r"tilda", "Tilda"),
]

DEPRECATED_TAGS = ["font", "center", "marquee", "blink", "frameset", "frame", "big", "tt"]

SOCIAL_META = ["og:title", "og:description", "og:image", "og:site_name"]


@dataclass
class Heuristics:
    outdated_score: int = 0
    signals: list[str] = field(default_factory=list)
    https: bool = False
    mobile_friendly: bool = False
    cms: str | None = None
    copyright_year: int | None = None
    title: str | None = None

    def add(self, points: int, signal: str) -> None:
        self.outdated_score += points
        self.signals.append(signal)


def _detect_cms(html_lower: str, soup: BeautifulSoup) -> str | None:
    generator = ""
    tag = soup.find("meta", attrs={"name": re.compile("generator", re.I)})
    if tag and tag.get("content"):
        generator = tag["content"]
    haystack = (generator + " " + html_lower).lower()
    for pattern, label in CMS_PATTERNS:
        if re.search(pattern, haystack):
            return label
    return None


def _find_copyright_year(text: str) -> int | None:
    """Ищет самый свежий год рядом со знаком копирайта."""
    years: list[int] = []
    for m in re.finditer(r"(?:©|\(c\)|copyright|&copy;|все права защищены)[^0-9]{0,40}(19|20)\d{2}", text, re.I):
        year = int(m.group(0)[-4:])
        if 1995 <= year <= CURRENT_YEAR:
            years.append(year)
    # Диапазоны вида «2008–2015» — берём правую границу
    for m in re.finditer(r"(20\d{2})\s*[–\-—]\s*(20\d{2})", text):
        year = int(m.group(2))
        if 1995 <= year <= CURRENT_YEAR:
            years.append(year)
    return max(years) if years else None


def analyze(
    html: str,
    *,
    final_url: str,
    headers: dict[str, str] | None = None,
) -> Heuristics:
    """Прогоняет страницу через все эвристики и считает балл."""
    headers = headers or {}
    result = Heuristics()
    soup = BeautifulSoup(html or "", "lxml")
    html_lower = (html or "").lower()
    text = soup.get_text(" ", strip=True) if html else ""

    title_tag = soup.find("title")
    result.title = title_tag.get_text(strip=True) if title_tag else None

    # 1. HTTPS
    result.https = final_url.startswith("https://")
    if not result.https:
        result.add(15, "нет HTTPS")

    # 2. Адаптивность: <meta name=viewport> — главный признак мобильной вёрстки
    viewport = soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)})
    result.mobile_friendly = viewport is not None
    if viewport is None:
        result.add(22, "нет meta viewport (не адаптивный)")

    # 3. Устаревший doctype / его отсутствие
    doctype = next(
        (item for item in soup.contents if getattr(item, "name", None) is None
         and str(item).strip().lower().startswith("<!doctype")),
        None,
    )
    doc_str = str(doctype).lower() if doctype else ""
    if not html_lower.lstrip().startswith("<!doctype"):
        result.add(7, "нет DOCTYPE")
    elif "html 4" in doc_str or "xhtml" in doc_str:
        result.add(7, "старый DOCTYPE (HTML4/XHTML)")

    # 4. Deprecated-теги
    found_tags = [t for t in DEPRECATED_TAGS if soup.find(t)]
    if found_tags:
        result.add(15, f"устаревшие теги: {', '.join(found_tags)}")

    # 5. Табличная вёрстка (много таблиц + width-атрибуты)
    tables = soup.find_all("table")
    tables_with_width = [t for t in tables if t.get("width")]
    if len(tables) >= 3 and tables_with_width:
        result.add(12, f"вёрстка на таблицах ({len(tables)} шт.)")
    elif re.search(r"bgcolor\s*=", html_lower):
        result.add(6, "атрибут bgcolor (старая вёрстка)")

    # 6. Flash
    if ".swf" in html_lower or soup.find("embed") or re.search(r"application/x-shockwave-flash", html_lower):
        result.add(15, "Flash-контент")

    # 7. Старый jQuery
    jq = re.search(r"jquery[-.](\d+)\.(\d+)(?:\.\d+)?(?:\.min)?\.js", html_lower)
    if jq:
        major, minor = int(jq.group(1)), int(jq.group(2))
        if major == 1 and minor < 9:
            result.add(6, f"старый jQuery {major}.{minor}")

    # 8. Копирайт в футере
    year = _find_copyright_year(text)
    result.copyright_year = year
    if year is not None:
        gap = CURRENT_YEAR - year
        if gap >= 3:
            result.add(min(12, 2 * gap), f"копирайт устарел (© {year})")

    # 9. Open Graph
    has_og = any(soup.find("meta", attrs={"property": re.compile(f"^{p}$", re.I)}) for p in SOCIAL_META)
    if not has_og:
        result.add(5, "нет Open Graph разметки")

    # 10. Favicon
    if not soup.find("link", attrs={"rel": re.compile("icon", re.I)}):
        result.add(3, "нет favicon")

    # 11. Media queries (адаптивность на уровне CSS во внешних/внутренних стилях)
    if "@media" not in html_lower and viewport is None:
        result.add(5, "нет @media-запросов")

    # 12. Старый серверный софт
    server = (headers.get("server") or "").lower()
    powered = (headers.get("x-powered-by") or "").lower()
    if re.search(r"php/[45]\.", powered) or re.search(r"php/[45]\.", server):
        result.add(6, f"старый PHP ({powered or server})")
    if re.search(r"apache/2\.2", server) or re.search(r"iis/[567]\.", server):
        result.add(4, f"старый веб-сервер ({server})")

    # 13. CMS / конструктор
    cms = _detect_cms(html_lower, soup)
    result.cms = cms
    if cms:
        low = cms.lower()
        if any(k in low for k in ("очень старая", "реликт", "1-3", "1.x", "2.x", "5-7")):
            result.add(10, f"устаревшая CMS: {cms}")

    result.outdated_score = min(100, result.outdated_score)
    return result
