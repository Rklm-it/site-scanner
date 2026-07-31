"""Оборот компании по ИНН через ГИР БО — государственный ресурс бухотчётности
ФНС (https://bo.nalog.gov.ru).

Первоисточник: именно сюда компании сдают бухгалтерскую отчётность, а платные
агрегаторы перепродают эти же цифры. Доступ открытый — ни ключа, ни лимитов,
ни тарифов. Поэтому он у нас основной источник выручки, а DataNewton остался
запасным (на бесплатном тарифе он финансы не отдаёт вовсе).

Схема, проверенная на живом API:

1. ``GET /advanced-search/organizations/search?query=<ИНН>`` → страница
   результатов Spring: ``{"content": [{"id": ..., "shortName": ...}], ...}``.
   Ищется только по ИНН и названию — ОГРН этот endpoint не понимает.
2. ``GET /nbo/organizations/<id>/bfo/`` → список сданных отчётов по годам:
   ``[{"period": "2025", "gainSum": 1980674, "actives": ...}, ...]``.

``gainSum`` — это строка 2110 «Выручка»: сверено с детализацией отчёта, где
``financialResult.current2110`` даёт то же число. Поэтому в детализацию
(``/nbo/bfo/<id>/details``) не ходим — хватает списка.

Чего тут нет: банков (у кредитных организаций своя отчётность) и ИП (они
бухотчётность не сдают в принципе).
"""

from __future__ import annotations

import re

import requests

BASE = "https://bo.nalog.gov.ru"
SEARCH_URL = f"{BASE}/advanced-search/organizations/search"
BFO_URL = f"{BASE}/nbo/organizations/{{org_id}}/bfo/"

# Суммы в отчётности — в тысячах рублей; приводим к рублям, как и у DataNewton.
THOUSANDS = 1000

# В названиях API возвращает HTML-подсветку совпадения: ООО "<strong>ГЕПАРД</strong>"
_TAGS = re.compile(r"<[^>]+>")

_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "application/json",
}


def _clean(name: str | None) -> str:
    return _TAGS.sub("", name or "").strip()


def find_org_id(inn: str, *, session: requests.Session | None = None,
                timeout: float = 20.0) -> tuple[int | None, str | None]:
    """id организации в ГИР БО по ИНН → (id, ошибка)."""
    sess = session or requests
    try:
        resp = sess.get(SEARCH_URL, params={"query": inn, "page": 0},
                        headers=_HEADERS, timeout=timeout)
    except requests.RequestException as exc:
        return None, f"нет связи с ГИР БО: {exc}"
    if resp.status_code != 200:
        return None, f"ГИР БО вернул HTTP {resp.status_code}"
    try:
        content = (resp.json() or {}).get("content") or []
    except ValueError:
        return None, "ГИР БО прислал не-JSON ответ"
    if not content:
        return None, ("компания не найдена в ГИР БО — там нет банков и ИП, "
                      "а новые ООО появляются после первой сданной отчётности")

    # Поиск понимает и название, поэтому не берём первое попавшееся вслепую:
    # если ИНН в ответе есть, он должен совпасть с запрошенным.
    for item in content:
        if not item.get("inn") or str(item["inn"]) == str(inn):
            org_id = item.get("id")
            if org_id is not None:
                return int(org_id), None
    return None, "ГИР БО вернул другие компании — совпадения по ИНН нет"


def latest_revenue(reports: list[dict]) -> int | None:
    """Выручка (руб.) за самый свежий год из списка отчётов."""
    years = [
        (int(r["period"]), r["gainSum"])
        for r in reports
        if str(r.get("period", "")).isdigit()
        and isinstance(r.get("gainSum"), (int, float)) and r["gainSum"] > 0
    ]
    if not years:
        return None
    years.sort()
    return int(round(years[-1][1] * THOUSANDS))


def revenue_by_inn(inn: str, *, session: requests.Session | None = None,
                   timeout: float = 20.0) -> tuple[int | None, str | None]:
    """Выручка (руб.) за последний отчётный год по ИНН → (сумма, ошибка).

    ``сумма`` = None, если отчётности нет; ``ошибка`` заполняется только когда
    причина внешняя (нет связи, сервис ответил не тем), чтобы отличать
    «не публиковала» от «не смогли спросить».
    """
    if not inn:
        return None, None

    org_id, err = find_org_id(inn, session=session, timeout=timeout)
    if org_id is None:
        return None, err

    sess = session or requests
    try:
        resp = sess.get(BFO_URL.format(org_id=org_id), headers=_HEADERS, timeout=timeout)
    except requests.RequestException as exc:
        return None, f"нет связи с ГИР БО: {exc}"
    if resp.status_code != 200:
        return None, f"ГИР БО вернул HTTP {resp.status_code} по отчётности"
    try:
        reports = resp.json() or []
    except ValueError:
        return None, "ГИР БО прислал не-JSON ответ по отчётности"
    if not isinstance(reports, list) or not reports:
        return None, "компания есть в ГИР БО, но отчётность не сдавала"

    revenue = latest_revenue(reports)
    if revenue is None:
        return None, "в отчётности ГИР БО нет строки «Выручка» за отчётные годы"
    return revenue, None
