#!/usr/bin/env python3
"""Кому звонить: разбор базы лидов по критериям из clients/README.md.

Запуск на сервере владельца:

    docker compose exec app python /app/clients/komu_zvonit.py

Зачем скрипт, а не глазами по выгрузке. Критерии отбора давно записаны в
`clients/README.md`, но применялись вручную и по памяти — а это ровно то
место, где ошибка стоит живого звонка не туда. Один раз случай уже был:
`print-rf.ru` показал карточку чужой компании, потому что ИНН на сайте не
нашёлся и DaData подтянула похожую по названию. Скрипт такое помечает сам.

Ничего не решает за владельца: он раскладывает лидов по трём кучам с
объяснением, почему каждый туда попал. Решение всё равно за человеком.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

DB = "/data/webapp_data/leads.sqlite"

# Статусы, по которым лид уже в работе: их в список на обзвон не берём.
# «отказ» тоже: к нему возвращаются через месяцы, и это отдельный разговор.
WORKED = {"написал", "звонил", "недозвон", "перезвонить", "интерес",
          "ответили", "клиент", "отказ", "мусор"}

# Признаки магазина. Переделка магазина — от 250 тысяч и почти всегда со
# своим подрядчиком, для холодного звонка это мимо.
SHOP = re.compile(r"корзин|/cart|/basket|интернет-магазин|каталог товаров", re.I)

# Порталы и агрегаторы: собирают трафик по локальным запросам и лезут в
# выдачу, но своего бизнеса за ними нет.
PORTAL = re.compile(
    r"^(www\.)?(gov|.*\.gov|[^.]*catalog|[^.]*portal|[^.]*top|[^.]*otzyv|"
    r"[^.]*spravka|[^.]*reklam|2gis|yell|zoon|blizko|flamp|avito|youla)\.",
    re.I,
)


def money(v) -> str:
    try:
        n = float(v)
    except (TypeError, ValueError):
        return "—"
    return f"{n / 1_000_000:.1f} млн" if n else "—"


def verdict(r: dict) -> tuple[str, list[str], int]:
    """Куда лида: «звонить», «проверить» или «мимо». Плюс причины и вес
    для сортировки внутри кучи."""
    plus: list[str] = []
    minus: list[str] = []
    stop: list[str] = []

    domain = (r.get("domain") or "").lower()
    outdated = int(r.get("outdated_score") or 0)
    revenue = r.get("revenue")
    revenue = float(revenue) if str(revenue).replace(".", "", 1).isdigit() else None
    inn = (r.get("inn") or "").strip()
    company = (r.get("company") or "").strip()
    phones = [p for p in (r.get("phones") or "").split(",") if p.strip()]
    emails = [e for e in (r.get("emails") or "").split(",") if e.strip()]

    # --- отсев ---
    if PORTAL.match(domain):
        stop.append("портал или агрегатор")
    if not phones:
        stop.append("нет телефона — звонить некуда")
    if SHOP.search((r.get("signals") or "") + " " + (r.get("title") or "")):
        stop.append("похоже на интернет-магазин")
    if r.get("is_individual") == "да" and (revenue or 0) < 5_000_000:
        stop.append("ИП с малым оборотом")
    if (r.get("company_status") or "").lower().startswith(("ликвид", "недейств")):
        stop.append(f"компания {r['company_status']}")

    # --- балл старости: рабочее окно 45–65 ---
    if outdated >= 75:
        minus.append(f"балл {outdated} — часто это мёртвый сайт, проверить до звонка")
    elif 45 <= outdated <= 65:
        plus.append(f"балл {outdated} — рабочее окно")
    elif outdated < 45:
        minus.append(f"балл {outdated} — сайт не так уж плох, зацепок мало")
    else:
        plus.append(f"балл {outdated}")

    # --- деньги ---
    if revenue is not None and revenue > 0:
        if 10_000_000 <= revenue <= 100_000_000:
            plus.append(f"оборот {money(revenue)} — попадает в вилку")
        elif revenue > 100_000_000:
            plus.append(f"оборот {money(revenue)} — крупный, но решение будет долгим")
        else:
            minus.append(f"оборот {money(revenue)} — маловат под наш чек")

    # --- достоверность карточки ---
    if company and not inn:
        minus.append("ДАННЫЕ ПО НАЗВАНИЮ, ИНН нет — компания может быть чужой")

    # --- прочие плюсы ---
    if r.get("corp_email") == "да":
        plus.append("почта на своём домене")
    if (r.get("marketing") or "").strip():
        plus.append(f"вкладывается в рекламу: {r['marketing'][:40]}")
    if r.get("mobile_friendly") == "нет":
        plus.append("не работает на телефоне")
    if r.get("https") == "нет" or r.get("tls_error") == "да":
        plus.append("проблемы с https")
    if not emails:
        minus.append("почты нет, только звонок")

    if stop:
        return "мимо", stop, 0
    # Вес: чем больше плюсов и чем ближе балл к середине окна, тем выше
    weight = len(plus) * 10 - len(minus) * 6 - abs(outdated - 55)
    if revenue and 10_000_000 <= revenue <= 100_000_000:
        weight += 15
    bucket = "проверить" if any(m.startswith("ДАННЫЕ") for m in minus) or outdated >= 75 else "звонить"
    return bucket, plus + minus, weight


def main() -> int:
    ap = argparse.ArgumentParser(description="Кому звонить из базы лидов")
    ap.add_argument("--db", default=DB)
    ap.add_argument("--limit", type=int, default=20, help="сколько показать в каждой куче")
    ap.add_argument("--all", action="store_true", help="включая тех, с кем уже работали")
    args = ap.parse_args()

    if not Path(args.db).exists():
        print(f"Базы нет: {args.db}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(args.db)
    state = {}
    try:
        state = {d: s for d, s in conn.execute("SELECT domain, status FROM lead_state")}
    except sqlite3.Error:
        pass

    buckets: dict[str, list] = {"звонить": [], "проверить": [], "мимо": []}
    total = 0
    for (data,) in conn.execute("SELECT data FROM leads"):
        r = json.loads(data)
        total += 1
        st = state.get(r.get("domain"), "")
        if st in WORKED and not args.all:
            continue
        b, why, w = verdict(r)
        buckets[b].append((w, r, why))

    print(f"В базе {total} лидов. Уже в работе: "
          f"{sum(1 for s in state.values() if s in WORKED)}.\n")

    for name, title in (("звонить", "★ ЗВОНИТЬ"),
                        ("проверить", "⚠ СНАЧАЛА ПРОВЕРИТЬ"),
                        ("мимо", "✗ МИМО")):
        rows = sorted(buckets[name], key=lambda x: -x[0])
        print(f"\n{'=' * 72}\n{title} — {len(rows)}\n{'=' * 72}")
        for w, r, why in rows[:args.limit]:
            phone = (r.get("phones") or "").split(",")[0].strip() or "—"
            print(f"\n{r.get('domain','')}  |  {phone}  |  балл {r.get('outdated_score','?')}"
                  f"  |  {money(r.get('revenue'))}")
            if r.get("company"):
                print(f"  {r['company']}" + (f"  ИНН {r['inn']}" if r.get("inn") else "  (ИНН нет)"))
            for line in why:
                print(f"    · {line}")
        if len(rows) > args.limit:
            print(f"\n  … и ещё {len(rows) - args.limit}. Показать все: --limit 999")

    print("\nНапоминание: карточку без ИНН перед звонком проверять вручную —")
    print("DaData ищет по названию и возвращает похожее, а не точное.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
