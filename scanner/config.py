"""Настройки прогона: значения по умолчанию + загрузка из YAML."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path

import yaml


@dataclass
class Settings:
    # источник запросов
    queries: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    cities: list[str] = field(default_factory=list)

    # поиск
    providers: list[str] = field(default_factory=lambda: ["yandex", "google"])
    max_per_query: int = 20
    # Домены, помеченные в базе как мусор: брошенные сайты, переехавшие
    # компании, агрегаторы. Один раз отметил — больше не попадается.
    skip_domains: list[str] = field(default_factory=list)

    # скан
    concurrency: int = 16
    min_score: int = 0
    timeout: float = 8.0
    follow_contact_page: bool = True

    # потолки времени (сек). Прогон не может идти дольше total_budget: каждая
    # фаза берёт не больше своего бюджета И не больше остатка от общего.
    total_budget: float = 1800.0       # весь прогон целиком
    collect_budget: float = 240.0      # сбор выдачи из поисковиков
    scan_budget: float | None = None   # фаза скана сайтов; None — авто от объёма
    enrich_budget: float = 600.0       # обогащение через DaData/DataNewton

    # вежливость
    respect_robots: bool = True
    per_host_delay: float = 0.5

    # обогащение по ИНН (DaData)
    enrich: bool = False

    # кэш
    cache_path: str | None = "cache.sqlite"
    cache_pages: bool = False
    skip_seen: bool = False
    search_ttl: int = 86_400
    page_ttl: int = 86_400

    # вывод
    out: str = "leads"
    top: int = 0

    @classmethod
    def load(cls, path: str | Path) -> "Settings":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"Неизвестные ключи в конфиге: {', '.join(sorted(unknown))}")
        return cls(**data)
