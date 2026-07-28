"""Аналитика лидов для аутрича: кому выгоднее писать предложение о сайте.

Идея: лучший адресат письма с предложением сделать сайт — это компания,
у которой (а) есть куда писать, желательно рабочая почта на своём домене,
(б) сайт реально устарел, (в) есть деньги (оборот) и она действующая.
Из этих сигналов складывается ``outreach_score`` (0..100) и приоритет A/B/C.
"""

from __future__ import annotations

from collections import Counter

import tldextract

from .models import Lead

# Бесплатные/публичные почтовые домены — это НЕ рабочая почта на своём домене.
FREE_EMAIL_DOMAINS = {
    "gmail.com", "mail.ru", "yandex.ru", "ya.ru", "bk.ru", "list.ru", "inbox.ru",
    "rambler.ru", "internet.ru", "mail.com", "outlook.com", "hotmail.com",
    "icloud.com", "yahoo.com", "protonmail.com", "vk.com",
}

REVENUE_BUDGET_THRESHOLD = 10_000_000  # оборот, выше которого считаем «есть бюджет»


def _reg_domain(host: str) -> str:
    ext = tldextract.extract(host)
    return ".".join(p for p in (ext.domain, ext.suffix) if p)


def has_corporate_email(lead: Lead) -> bool:
    """True, если есть email на собственном домене сайта (рабочая почта)."""
    site = lead.domain or _reg_domain(lead.final_url or lead.url or "")
    for email in lead.contacts.emails:
        if "@" not in email:
            continue
        edomain = email.rsplit("@", 1)[1].lower()
        if edomain in FREE_EMAIL_DOMAINS:
            continue
        if _reg_domain(edomain) == site:
            return True
    return False


def _is_active(status: str | None) -> bool:
    if not status:
        return False
    s = status.upper()
    return "ACTIVE" in s or "ДЕЙСТВ" in s


def outreach_score(lead: Lead) -> tuple[int, str]:
    """Считает балл аутрича (0..100) и приоритет A/B/C.

    Логика: лучший клиент — тот, до кого можно достучаться (почта),
    у кого сайт устарел И кто при этом ВКЛАДЫВАЕТСЯ в клиентов (реклама/
    аналитика) или имеет оборот. «Просто старый» сайт без признаков жизни
    часто заброшен — такой ниже.
    """
    score = 0.0

    # 1. Достижимость по почте (до 30)
    if has_corporate_email(lead):
        score += 30
        lead.corporate_email = True
    elif lead.contacts.emails:
        score += 18
    elif lead.contacts.phones:
        score += 7

    # 2. Потребность — насколько устарел сайт (до 30)
    score += lead.outdated_score * 0.30

    # 3. Бюджет и «живость» бизнеса (до 40)
    e = lead.enrichment
    budget = 0
    if e.revenue is not None:
        budget += 18 if e.revenue >= REVENUE_BUDGET_THRESHOLD else 10
    else:
        budget += 4  # оборот неизвестен — нейтрально
    if _is_active(e.status):
        budget += 4
    if e.employee_count:
        budget += 4
    if lead.marketing:            # вкладывается в рекламу/аналитику — сильный сигнал
        budget += 14
    score += min(budget, 40)

    total = int(round(min(100, score)))
    tier = "A" if total >= 70 else "B" if total >= 45 else "C"
    return total, tier


def annotate(leads: list[Lead]) -> None:
    """Проставляет каждому лиду outreach_score / outreach_tier / corporate_email."""
    for lead in leads:
        lead.corporate_email = False
        lead.outreach_score, lead.outreach_tier = outreach_score(lead)


def summarize(leads: list[Lead]) -> dict:
    """Сводка по прогону для панели аналитики."""
    total = len(leads)
    tiers = Counter(l.outreach_tier for l in leads)
    with_email = sum(1 for l in leads if l.contacts.emails)
    corp = sum(1 for l in leads if l.corporate_email)
    with_phone = sum(1 for l in leads if l.contacts.phones)
    with_revenue = sum(1 for l in leads if l.enrichment.revenue is not None)
    active = sum(1 for l in leads if _is_active(l.enrichment.status))
    invests_marketing = sum(1 for l in leads if l.marketing)
    avg_outdated = round(sum(l.outdated_score for l in leads) / total) if total else 0

    by_category = Counter(l.source_query for l in leads if l.source_query)

    return {
        "total": total,
        "tier_a": tiers.get("A", 0),
        "tier_b": tiers.get("B", 0),
        "tier_c": tiers.get("C", 0),
        "with_email": with_email,
        "corporate_email": corp,
        "with_phone": with_phone,
        "with_revenue": with_revenue,
        "active": active,
        "invests_marketing": invests_marketing,
        "avg_outdated": avg_outdated,
        "top_categories": by_category.most_common(8),
        # Готовы к письму на рабочую почту прямо сейчас
        "ready_to_email": sum(1 for l in leads if l.corporate_email and l.outreach_tier in ("A", "B")),
    }
