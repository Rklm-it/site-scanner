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

    # скан
    concurrency: int = 16
    min_score: int = 0
    timeout: float = 8.0
    scan_budget: float | None = None   # потолок времени на фазу скана (сек); None — авто
    follow_contact_page: bool = True

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
