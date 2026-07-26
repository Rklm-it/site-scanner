"""Модели данных для результатов скана."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Contacts:
    """Контактные данные, вытащенные со страницы."""

    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    socials: list[str] = field(default_factory=list)
    inn: str | None = None
    ogrn: str | None = None
    company: str | None = None
    contact_page: str | None = None


@dataclass
class Lead:
    """Один просканированный сайт — потенциальный клиент."""

    url: str
    final_url: str | None = None
    domain: str = ""
    http_status: int | None = None
    error: str | None = None

    # Оценка устаревания дизайна (0..100, больше = древнее = лучше лид)
    outdated_score: int = 0
    signals: list[str] = field(default_factory=list)

    # Технические флаги
    https: bool = False
    mobile_friendly: bool = False
    cms: str | None = None
    copyright_year: int | None = None
    load_ms: int | None = None

    title: str | None = None
    contacts: Contacts = field(default_factory=Contacts)

    # Из какого поискового запроса пришёл сайт
    source_query: str | None = None

    def to_row(self) -> dict[str, Any]:
        """Плоская строка для CSV."""
        c = self.contacts
        return {
            "outdated_score": self.outdated_score,
            "domain": self.domain,
            "url": self.final_url or self.url,
            "company": c.company or "",
            "title": self.title or "",
            "https": "да" if self.https else "нет",
            "mobile_friendly": "да" if self.mobile_friendly else "нет",
            "cms": self.cms or "",
            "copyright_year": self.copyright_year or "",
            "emails": ", ".join(c.emails),
            "phones": ", ".join(c.phones),
            "socials": ", ".join(c.socials),
            "inn": c.inn or "",
            "ogrn": c.ogrn or "",
            "http_status": self.http_status or "",
            "load_ms": self.load_ms or "",
            "signals": "; ".join(self.signals),
            "source_query": self.source_query or "",
            "error": self.error or "",
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
