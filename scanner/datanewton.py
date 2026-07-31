"""Оборот компании по ИНН через DataNewton (бесплатный тариф отдаёт финансы).

DaData на бесплатном тарифе выручку не отдаёт, а DataNewton — да. Берём у него
только оборот (код строки 2110 «Выручка» из отчёта о финрезультатах), а название
и руководителя оставляем DaData.

Ключ — бесплатный, из личного кабинета https://datanewton.ru (env ``DATANEWTON_TOKEN``).
"""

from __future__ import annotations

import os

import requests

FINANCE_URL = "https://api.datanewton.ru/v1/finance"

# Росстат отдаёт суммы в тысячах рублей — приводим к рублям для единообразия с DaData.
THOUSANDS = 1000
REVENUE_CODE = "2110"   # «Выручка» в отчёте о финансовых результатах


def _find_by_code(node, target: str):
    """Рекурсивно ищет в дереве отчётности узел с нужным кодом строки."""
    if isinstance(node, dict):
        if str(node.get("code")) == target:
            return node
        for value in node.values():
            found = _find_by_code(value, target)
            if found is not None:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_by_code(item, target)
            if found is not None:
                return found
    return None


def _latest_revenue(data: dict) -> int | None:
    """Достаёт выручку за самый свежий отчётный год (в рублях)."""
    node = _find_by_code(data.get("fin_results") or {}, REVENUE_CODE)
    if not node:
        return None
    sums = node.get("sum") or {}
    # только годы с положительной выручкой; берём самый поздний
    years = [(int(y), v) for y, v in sums.items()
             if str(y).isdigit() and isinstance(v, (int, float)) and v > 0]
    if not years:
        return None
    years.sort()
    return int(round(years[-1][1] * THOUSANDS))


def revenue_by_inn(inn: str, *, token: str | None = None,
                   session: requests.Session | None = None) -> tuple[int | None, str | None]:
    """Выручка (руб.) за последний год по ИНН → (сумма, ошибка).

    ``сумма`` = None, если данных нет; ``ошибка`` заполняется только при
    проблемах доступа (плохой ключ, лимит), чтобы отличать «нет данных» от «нет доступа».
    """
    token = token or os.environ.get("DATANEWTON_TOKEN")
    if not (inn and token):
        return None, None
    sess = session or requests
    try:
        resp = sess.get(FINANCE_URL, params={"key": token, "inn": inn}, timeout=20)
    except requests.RequestException as exc:
        return None, f"нет связи с DataNewton: {exc}"
    if resp.status_code in (401, 403):
        return None, f"DataNewton отклонил ключ ({resp.status_code}) — проверьте API-ключ"
    if resp.status_code == 429:
        return None, "DataNewton: превышен лимит запросов (429)"
    if resp.status_code != 200:
        return None, f"DataNewton вернул HTTP {resp.status_code}"
    try:
        data = resp.json()
    except ValueError:
        return None, "DataNewton прислал не-JSON ответ"

    # Пустой ответ и «нет строки Выручка» — разные вещи, и ни одна из них не
    # означает «компания не публиковала отчётность»: так же выглядит тариф без
    # финансов и сменившаяся структура ответа. Не выдаём догадку за факт.
    if not isinstance(data, dict) or not data.get("fin_results"):
        return None, ("DataNewton не отдал финотчёт по этому ИНН — компания не публиковала "
                      "отчётность либо тариф ключа не включает финансы")
    revenue = _latest_revenue(data)
    if revenue is None:
        return None, "в отчёте DataNewton нет строки «Выручка» (код 2110)"
    return revenue, None
