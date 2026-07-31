"""Выгрузка результатов в CSV и JSON."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import Lead

CSV_COLUMNS = [
    "priority", "outreach_score", "outdated_score", "corp_email", "marketing",
    "domain", "url", "company",
    "revenue", "revenue_note", "is_individual", "company_status", "employees", "management",
    "title", "https", "tls_error", "mobile_friendly", "cms", "copyright_year",
    "emails", "phones", "socials", "inn", "ogrn", "reg_date", "address",
    "http_status", "load_ms", "signals", "source_query", "error",
]


def write_csv(leads: list[Lead], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for lead in leads:
            writer.writerow(lead.to_row())
    return path


def write_json(leads: list[Lead], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump([lead.to_dict() for lead in leads], f, ensure_ascii=False, indent=2)
    return path
