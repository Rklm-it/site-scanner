"""Обогащение лида данными о компании по ИНН через DaData.

Это тот самый шаг «смотришь оборот» из исходной идеи: по ИНН со страницы
достаём официальное название, статус (действующая/ликвидирована), оборот,
число сотрудников и руководителя. Позволяет поднимать в топ не просто
старые сайты, а старые сайты у компаний с деньгами.

Нужен бесплатный токен DaData (env ``DADATA_TOKEN``):
https://dadata.ru/api/find-party/
"""

from __future__ import annotations

import os
import sys

import requests

from .models import Enrichment

DADATA_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party"
DADATA_SUGGEST = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/party"

_warned = False


def _warn_once(message: str) -> None:
    global _warned
    if not _warned:
        _warned = True
        print(f"[enrich] {message}", file=sys.stderr)


def enrich_by_inn(inn: str, *, token: str | None = None, session: requests.Session | None = None) -> Enrichment:
    """Возвращает данные компании по ИНН. При отсутствии токена/данных — пустой Enrichment."""
    token = token or os.environ.get("DADATA_TOKEN")
    result = Enrichment()
    if not inn:
        return result
    if not token:
        _warn_once("обогащение по ИНН пропущено: задайте DADATA_TOKEN (https://dadata.ru/api/find-party/)")
        return result

    sess = session or requests
    try:
        resp = sess.post(
            DADATA_URL,
            json={"query": inn, "count": 1},
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Token {token}",
            },
            timeout=15,
        )
        resp.raise_for_status()
        suggestions = resp.json().get("suggestions") or []
    except (requests.RequestException, ValueError) as exc:
        _warn_once(f"ошибка DaData: {exc}")
        return result

    if not suggestions:
        return result
    return parse_party(suggestions[0].get("data") or {})


def enrich_by_name(name: str, *, token: str | None = None,
                   session: requests.Session | None = None) -> Enrichment:
    """Ищет компанию по названию (когда ИНН на сайте нет). Берёт лучшее совпадение."""
    token = token or os.environ.get("DADATA_TOKEN")
    if not (name and name.strip() and token):
        return Enrichment()
    sess = session or requests
    try:
        resp = sess.post(
            DADATA_SUGGEST,
            json={"query": name.strip(), "count": 1},
            headers={"Content-Type": "application/json", "Accept": "application/json",
                     "Authorization": f"Token {token}"},
            timeout=15,
        )
        resp.raise_for_status()
        suggestions = resp.json().get("suggestions") or []
    except (requests.RequestException, ValueError) as exc:
        _warn_once(f"ошибка DaData (по названию): {exc}")
        return Enrichment()
    if not suggestions:
        return Enrichment()
    return parse_party(suggestions[0].get("data") or {})


def lookup(inn: str | None = None, name: str | None = None, *, token: str | None = None,
           session: requests.Session | None = None) -> Enrichment:
    """Единый чек компании: сначала по ИНН, при отсутствии данных — по названию."""
    e = Enrichment()
    if inn:
        e = enrich_by_inn(inn, token=token, session=session)
    if (e.revenue is None and not e.official_name) and name:
        e = enrich_by_name(name, token=token, session=session)
    return e


def _dadata_post(url: str, payload: dict, token: str,
                 session: requests.Session | None) -> tuple[dict | None, str | None]:
    """POST в DaData → (json, ошибка). Ошибку формулируем понятно."""
    sess = session or requests
    try:
        resp = sess.post(
            url, json=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json",
                     "Authorization": f"Token {token}"},
            timeout=15,
        )
    except requests.RequestException as exc:
        return None, f"нет связи с DaData: {exc}"
    if resp.status_code in (401, 403):
        return None, (f"DaData отклонил ключ ({resp.status_code}) — вставьте именно "
                      f"API-ключ (не секретный) и проверьте, что он активен")
    if resp.status_code == 429:
        return None, "DaData: превышен дневной лимит запросов (429)"
    if resp.status_code != 200:
        return None, f"DaData вернул HTTP {resp.status_code}"
    try:
        return resp.json(), None
    except ValueError:
        return None, "DaData прислал не-JSON ответ"


def lookup_verbose(inn: str | None = None, name: str | None = None, *,
                   token: str | None = None,
                   session: requests.Session | None = None) -> tuple[Enrichment, str | None]:
    """Как lookup(), но возвращает и текст ошибки DaData (для диагностики в UI)."""
    token = token or os.environ.get("DADATA_TOKEN")
    if not token:
        return Enrichment(), "не задан ключ DaData"
    if inn:
        data, err = _dadata_post(DADATA_URL, {"query": inn, "count": 1}, token, session)
        if err:
            return Enrichment(), err
        sugg = data.get("suggestions") or []
        if sugg:
            return parse_party(sugg[0].get("data") or {}), None
    if name:
        data, err = _dadata_post(DADATA_SUGGEST, {"query": name, "count": 1}, token, session)
        if err:
            return Enrichment(), err
        sugg = data.get("suggestions") or []
        if sugg:
            return parse_party(sugg[0].get("data") or {}), None
    return Enrichment(), None


def parse_party(data: dict) -> Enrichment:
    """Разбирает блок ``data`` из ответа DaData в Enrichment."""
    e = Enrichment()

    name = data.get("name") or {}
    e.official_name = name.get("short_with_opf") or name.get("full_with_opf")

    state = data.get("state") or {}
    e.status = state.get("status")
    reg_ts = state.get("registration_date")
    if reg_ts:
        import datetime
        e.registration_date = datetime.date.fromtimestamp(reg_ts / 1000).isoformat()

    finance = data.get("finance") or {}
    income = finance.get("income")
    if income is not None:
        e.revenue = int(income)

    employee = data.get("employee_count")
    if employee is not None:
        e.employee_count = int(employee)

    mgmt = data.get("management") or {}
    e.management = mgmt.get("name")

    address = data.get("address") or {}
    e.address = address.get("value")

    return e
