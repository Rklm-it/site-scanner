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

    def merge(self, other: "Contacts") -> None:
        """Дополняет контакты данными с другой страницы (напр. /контакты)."""
        self.emails = list(dict.fromkeys([*self.emails, *other.emails]))[:8]
        self.phones = list(dict.fromkeys([*self.phones, *other.phones]))[:8]
        self.socials = list(dict.fromkeys([*self.socials, *other.socials]))[:10]
        self.inn = self.inn or other.inn
        self.ogrn = self.ogrn or other.ogrn
        self.company = self.company or other.company
        self.contact_page = self.contact_page or other.contact_page


@dataclass
class Enrichment:
    """Данные о компании из внешнего реестра (DaData по ИНН)."""

    official_name: str | None = None
    status: str | None = None          # ДЕЙСТВУЮЩАЯ / ЛИКВИДИРОВАНА / ...
    revenue: int | None = None         # оборот (доход) за последний год, руб.
    employee_count: int | None = None
    registration_date: str | None = None
    management: str | None = None       # ФИО руководителя
    address: str | None = None


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
    tls_error: bool = False
    mobile_friendly: bool = False
    cms: str | None = None
    copyright_year: int | None = None
    load_ms: int | None = None

    title: str | None = None
    contacts: Contacts = field(default_factory=Contacts)
    enrichment: Enrichment = field(default_factory=Enrichment)

    # Аналитика для аутрича (насколько выгодно писать предложение)
    outreach_score: int = 0
    outreach_tier: str = ""          # A / B / C
    corporate_email: bool = False    # есть email на собственном домене

    # Из какого поискового запроса пришёл сайт
    source_query: str | None = None

    def to_row(self) -> dict[str, Any]:
        """Плоская строка для CSV."""
        c = self.contacts
        e = self.enrichment
        return {
            "priority": self.outreach_tier,
            "outreach_score": self.outreach_score,
            "outdated_score": self.outdated_score,
            "corp_email": "да" if self.corporate_email else "",
            "domain": self.domain,
            "url": self.final_url or self.url,
            "company": e.official_name or c.company or "",
            "revenue": e.revenue if e.revenue is not None else "",
            "company_status": e.status or "",
            "employees": e.employee_count if e.employee_count is not None else "",
            "management": e.management or "",
            "title": self.title or "",
            "https": "да" if self.https else "нет",
            "tls_error": "да" if self.tls_error else "",
            "mobile_friendly": "да" if self.mobile_friendly else "нет",
            "cms": self.cms or "",
            "copyright_year": self.copyright_year or "",
            "emails": ", ".join(c.emails),
            "phones": ", ".join(c.phones),
            "socials": ", ".join(c.socials),
            "inn": c.inn or "",
            "ogrn": c.ogrn or "",
            "reg_date": e.registration_date or "",
            "address": e.address or "",
            "http_status": self.http_status or "",
            "load_ms": self.load_ms or "",
            "signals": "; ".join(self.signals),
            "source_query": self.source_query or "",
            "error": self.error or "",
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
