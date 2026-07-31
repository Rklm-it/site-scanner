"""CLI: python -m scanner ..."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import __version__
from .config import Settings
from .pipeline import run
from .report import write_csv, write_json


def _apply_cli(settings: Settings, args: argparse.Namespace) -> Settings:
    """Накатывает флаги CLI поверх конфига (заданные флаги побеждают)."""
    if args.query:
        settings.queries = list(dict.fromkeys([*settings.queries, *args.query]))
    if args.queries_file:
        text = Path(args.queries_file).read_text(encoding="utf-8")
        settings.queries += [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("#")]
    if args.category:
        settings.categories = list(dict.fromkeys([*settings.categories, *args.category]))
    if args.city:
        settings.cities = list(dict.fromkeys([*settings.cities, *args.city]))

    if args.provider:
        settings.providers = args.provider
    for name in ("max_per_query", "concurrency", "min_score", "timeout", "out", "top",
                 "per_host_delay", "cache_path", "search_ttl", "total_budget"):
        val = getattr(args, name)
        if val is not None:
            setattr(settings, name, val)

    if args.no_robots:
        settings.respect_robots = False
    if args.no_cache:
        settings.cache_path = None
    if args.cache_pages:
        settings.cache_pages = True
    if args.skip_seen:
        settings.skip_seen = True
    if args.enrich:
        settings.enrich = True
    if args.no_follow_contacts:
        settings.follow_contact_page = False
    return settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scanner",
        description="Поиск клиентов веб-студии по устаревшему дизайну сайтов (Яндекс + Google).",
    )
    parser.add_argument("--version", action="version", version=f"site-scanner {__version__}")
    parser.add_argument("--config", help="YAML-конфиг (см. config.example.yaml)")
    parser.add_argument("-v", "--verbose", action="store_true", help="подробный лог")

    src = parser.add_argument_group("источник запросов")
    src.add_argument("-q", "--query", action="append", help="поисковый запрос (можно несколько раз)")
    src.add_argument("--queries-file", help="файл со списком запросов (по одному на строку)")
    src.add_argument("--category", action="append", help="категория бизнеса, напр. 'стоматология'")
    src.add_argument("--city", action="append", help="город (комбинируется с каждой категорией)")

    scan = parser.add_argument_group("параметры скана")
    scan.add_argument("--provider", action="append",
                      choices=["yandex", "google", "serpapi_google", "serpapi_yandex", "duckduckgo"],
                      help="поисковый провайдер (можно несколько раз; по умолчанию yandex + google)")
    scan.add_argument("--max-per-query", type=int, help="сколько результатов брать на запрос")
    scan.add_argument("--concurrency", type=int, help="сколько сайтов сканировать параллельно")
    scan.add_argument("--min-score", type=int, help="минимальный балл устаревания для попадания в список")
    scan.add_argument("--timeout", type=float, help="таймаут запроса к сайту, сек")
    scan.add_argument("--total-budget", type=float,
                      help="потолок времени на весь прогон, сек (по умолчанию 1800)")
    scan.add_argument("--per-host-delay", type=float, help="пауза между запросами к одному домену, сек")
    scan.add_argument("--no-robots", action="store_true", help="не учитывать robots.txt")
    scan.add_argument("--no-follow-contacts", action="store_true", help="не заходить на страницу контактов")

    enr = parser.add_argument_group("обогащение")
    enr.add_argument("--enrich", action="store_true", help="обогатить лиды по ИНН через DaData (нужен DADATA_TOKEN)")

    cache = parser.add_argument_group("кэш")
    cache.add_argument("--cache-path", help="путь к SQLite-кэшу (по умолчанию cache.sqlite)")
    cache.add_argument("--no-cache", action="store_true", help="полностью отключить кэш")
    cache.add_argument("--cache-pages", action="store_true", help="кэшировать HTML страниц")
    cache.add_argument("--skip-seen", action="store_true", help="пропускать домены из прошлых прогонов")
    cache.add_argument("--search-ttl", type=int, help="сколько секунд хранить выдачу поиска")

    out = parser.add_argument_group("вывод")
    out.add_argument("-o", "--out", help="базовое имя файлов вывода (создаст .csv и .json)")
    out.add_argument("--top", type=int, help="показать топ-N в консоли")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    settings = Settings.load(args.config) if args.config else Settings()
    settings = _apply_cli(settings, args)

    if not (settings.queries or settings.categories):
        parser.error("не задано ни одного запроса. Используй --query / --queries-file / --category / --config")

    print(f"Провайдеры: {', '.join(settings.providers)} | обогащение: {'да' if settings.enrich else 'нет'}",
          file=sys.stderr)

    def progress(done: int, total: int) -> None:
        print(f"\r  просканировано {done}/{total}", end="", file=sys.stderr, flush=True)

    leads = run(settings, progress=progress)
    print("", file=sys.stderr)

    csv_path = write_csv(leads, f"{settings.out}.csv")
    json_path = write_json(leads, f"{settings.out}.json")

    print(f"Готово. Лидов: {len(leads)}")
    print(f"  CSV:  {csv_path}")
    print(f"  JSON: {json_path}")

    top = settings.top or (10 if leads else 0)
    if top and leads:
        print(f"\nТоп-{min(top, len(leads))} по устареванию:")
        for lead in leads[:top]:
            contact = (lead.contacts.phones or lead.contacts.emails or ["—"])[0]
            rev = f" | оборот {lead.enrichment.revenue:,}₽".replace(",", " ") if lead.enrichment.revenue else ""
            print(f"  {lead.outdated_score:>3}  {lead.domain:<30} {contact}{rev}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
