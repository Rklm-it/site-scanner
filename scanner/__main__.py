"""CLI: python -m scanner ..."""

from __future__ import annotations

import argparse
import sys
from itertools import product
from pathlib import Path

from . import __version__
from .pipeline import run
from .report import write_csv, write_json


def build_queries(args: argparse.Namespace) -> list[str]:
    queries: list[str] = list(args.query or [])

    if args.queries_file:
        text = Path(args.queries_file).read_text(encoding="utf-8")
        queries += [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]

    # Генерация «категория × город»
    if args.category:
        cities = args.city or [""]
        for category, city in product(args.category, cities):
            queries.append(f"{category} {city}".strip())

    # Уникализируем, сохраняя порядок
    return list(dict.fromkeys(queries))


def _progress(done: int, total: int) -> None:
    print(f"\r  просканировано {done}/{total}", end="", file=sys.stderr, flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scanner",
        description="Поиск потенциальных клиентов веб-студии по устаревшему дизайну сайтов.",
    )
    parser.add_argument("--version", action="version", version=f"site-scanner {__version__}")

    src = parser.add_argument_group("источник запросов")
    src.add_argument("-q", "--query", action="append", help="поисковый запрос (можно несколько раз)")
    src.add_argument("--queries-file", help="файл со списком запросов (по одному на строку)")
    src.add_argument("--category", action="append", help="категория бизнеса, напр. 'стоматология'")
    src.add_argument("--city", action="append", help="город (комбинируется с каждой категорией)")

    scan = parser.add_argument_group("параметры скана")
    scan.add_argument("--provider", default="duckduckgo",
                      choices=["duckduckgo", "google", "serpapi"],
                      help="поисковый провайдер (по умолчанию duckduckgo)")
    scan.add_argument("--max-per-query", type=int, default=20, help="сколько результатов брать на запрос")
    scan.add_argument("--concurrency", type=int, default=8, help="сколько сайтов сканировать параллельно")
    scan.add_argument("--min-score", type=int, default=0, help="минимальный балл устаревания для попадания в список")

    out = parser.add_argument_group("вывод")
    out.add_argument("-o", "--out", default="leads", help="базовое имя файлов вывода (создаст .csv и .json)")
    out.add_argument("--top", type=int, default=0, help="показать топ-N в консоли (0 — не показывать)")

    args = parser.parse_args(argv)

    queries = build_queries(args)
    if not queries:
        parser.error("не задано ни одного запроса. Используй --query / --queries-file / --category")

    print(f"Запросов: {len(queries)} | провайдер: {args.provider}", file=sys.stderr)
    leads = run(
        queries,
        provider=args.provider,
        max_per_query=args.max_per_query,
        concurrency=args.concurrency,
        min_score=args.min_score,
        progress=_progress,
    )
    print("", file=sys.stderr)

    csv_path = write_csv(leads, f"{args.out}.csv")
    json_path = write_json(leads, f"{args.out}.json")

    print(f"Готово. Лидов: {len(leads)}")
    print(f"  CSV:  {csv_path}")
    print(f"  JSON: {json_path}")

    top = args.top or (10 if leads else 0)
    if top and leads:
        print(f"\nТоп-{min(top, len(leads))} по устареванию:")
        for lead in leads[:top]:
            contact = lead.contacts.phones[0] if lead.contacts.phones else (
                lead.contacts.emails[0] if lead.contacts.emails else "—")
            print(f"  {lead.outdated_score:>3}  {lead.domain:<32} {contact}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
