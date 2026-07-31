"""Обогащение лида данными о компании: название/статус/директор — DaData,
оборот — ГИР БО (ФНС), с DataNewton как запасным источником.

Это тот самый шаг «смотришь оборот» из исходной идеи: по ИНН со страницы
достаём официальное название, статус (действующая/ликвидирована), оборот,
число сотрудников и руководителя. Позволяет поднимать в топ не просто
старые сайты, а старые сайты у компаний с деньгами.

DaData (env ``DADATA_TOKEN``, https://dadata.ru/api/find-party/) на бесплатном
тарифе отдаёт название, статус и ФИО руководителя, но НЕ выручку.

Оборот берём в ГИР БО (https://bo.nalog.gov.ru) — государственном ресурсе
бухотчётности ФНС: открыт, без ключа и без лимитов, и это первоисточник, из
которого агрегаторы данные и перепродают. DataNewton (env ``DATANEWTON_TOKEN``)
остался запасным: вопреки прежнему комментарию здесь, на бесплатном тарифе он
финансы не отдаёт — на запрос приходит 200 с ``{"available_count": 0}``.
"""

from __future__ import annotations

import os
import sys

import requests

from . import datanewton
from . import girbo
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
    """Единый чек компании: название/статус/директор (DaData) + оборот (DataNewton)."""
    e, _ = lookup_verbose(inn, name, token=token, session=session)
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
                   ogrn: str | None = None, token: str | None = None,
                   dn_token: str | None = None,
                   session: requests.Session | None = None) -> tuple[Enrichment, str | None]:
    """Как lookup(), но возвращает и текст ошибки (для диагностики в UI).

    DaData даёт название/статус/директора и резолвит ИНН по ИНН/ОГРН со страницы
    или по названию; затем DataNewton добирает оборот по этому ИНН.
    """
    token = token or os.environ.get("DADATA_TOKEN")
    dn_token = dn_token or os.environ.get("DATANEWTON_TOKEN")

    e = Enrichment()
    err: str | None = None
    resolved_inn = (inn or "").strip() or None

    # 1. Название/статус/директор из DaData: по ИНН, затем ОГРН, затем названию.
    if token:
        attempts = [(DADATA_URL, inn), (DADATA_URL, ogrn), (DADATA_SUGGEST, name)]
        for url, query in attempts:
            if not query or e.official_name:
                continue
            data, attempt_err = _dadata_post(url, {"query": query, "count": 1}, token, session)
            if attempt_err:
                # Раньше любая ошибка на первой попытке отменяла и поиск по ОГРН,
                # и поиск по названию — из-за одного сетевого сбоя лид оставался
                # без оборота. Запоминаем причину, но продолжаем пробовать.
                err = err or attempt_err
                if _is_fatal(attempt_err):
                    break          # плохой ключ или исчерпанный лимит — дальше без толку
                continue
            sugg = data.get("suggestions") or []
            if sugg:
                e = parse_party(sugg[0].get("data") or {})
                resolved_inn = resolved_inn or e.inn or None
                err = None         # получилось со второй/третьей попытки
    elif not resolved_inn:
        # Без ключа DaData оборот всё ещё достижим — ГИР БО работает по ИНН со
        # страницы и ключа не требует. Сдаёмся только если и ИНН нет.
        e.note = "не задан ключ DaData, а ИНН на сайте не нашёлся"
        return e, e.note

    # 2. У ИП оборота в реестрах нет — не тратим на них запрос к DataNewton.
    if e.is_individual:
        e.note = explain_revenue(e, err, inn=inn, ogrn=ogrn, name=name, dn_token=dn_token)
        return e, err

    # 3. Оборот. Сначала ГИР БО — первоисточник ФНС, бесплатный и без лимитов.
    # DataNewton остаётся запасным: на бесплатном тарифе он финансы не отдаёт
    # (отвечает 200 с {"available_count": 0} вместо отчёта).
    if e.revenue is None and resolved_inn:
        rev, gb_err = girbo.revenue_by_inn(resolved_inn, session=session)
        if rev is not None:
            e.revenue = rev
        elif dn_token:
            rev, dn_err = datanewton.revenue_by_inn(resolved_inn, token=dn_token, session=session)
            if rev is not None:
                e.revenue = rev
            elif not err:
                err = dn_err or gb_err
        elif not err:
            err = gb_err

    e.note = explain_revenue(e, err, inn=inn, ogrn=ogrn, name=name, dn_token=dn_token)
    return e, err


def _is_fatal(err: str) -> bool:
    """Ошибка, при которой остальные попытки бессмысленны: ключ или лимит."""
    return "отклонил ключ" in err or "лимит" in err


def explain_revenue(e: Enrichment, err: str | None = None, *, inn: str | None = None,
                    ogrn: str | None = None, name: str | None = None,
                    dn_token: str | None = None) -> str | None:
    """Почему у лида пустой оборот. ``None`` — оборот есть, объяснять нечего.

    Пустая ячейка «Оборот» сама по себе ничего не говорит: не найдена компания,
    ИП, нет отчётности и кончился лимит выглядят одинаково. Причину считаем один
    раз здесь — её используют и скан, и ручная проверка в интерфейсе.
    """
    if e.revenue is not None:
        return None
    if e.is_individual:
        return "ИП — выручки в реестрах нет"
    if err:
        return err
    if not (inn or ogrn or name):
        return "на сайте нет ни ИНН, ни названия компании — не по чему искать"
    if not e.official_name:
        by = "ИНН" if inn else "ОГРН" if ogrn else "названию с сайта"
        return f"компания не найдена в реестре по {by}"
    return "компания найдена, но источник не отдал выручку"


def parse_party(data: dict) -> Enrichment:
    """Разбирает блок ``data`` из ответа DaData в Enrichment."""
    e = Enrichment()

    e.inn = data.get("inn")
    e.is_individual = (data.get("type") == "INDIVIDUAL")

    name = data.get("name") or {}
    e.official_name = name.get("short_with_opf") or name.get("full_with_opf")
    fio = (data.get("fio") or {}).get("source")
    if not e.official_name and e.is_individual and fio:
        e.official_name = f"ИП {fio.title()}"

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
    # У ИП руководителя в реестре нет — «главный» это сам предприниматель.
    if not e.management and e.is_individual and fio:
        e.management = fio.title()

    address = data.get("address") or {}
    e.address = address.get("value")

    return e
