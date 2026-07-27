from scanner.analytics import has_corporate_email, outreach_score, annotate, summarize
from scanner.models import Lead, Contacts, Enrichment


def _lead(**kw):
    base = dict(url="https://firma.ru", domain="firma.ru", outdated_score=80)
    base.update(kw)
    return Lead(**base)


def test_corporate_email_on_own_domain():
    lead = _lead(contacts=Contacts(emails=["info@firma.ru"]))
    assert has_corporate_email(lead)


def test_free_email_is_not_corporate():
    lead = _lead(contacts=Contacts(emails=["firma2000@mail.ru"]))
    assert not has_corporate_email(lead)


def test_subdomain_email_still_corporate():
    lead = _lead(contacts=Contacts(emails=["sales@mail.firma.ru"]))
    assert has_corporate_email(lead)


def test_outreach_prioritizes_corp_email_old_site_with_revenue():
    hot = _lead(
        outdated_score=90,
        contacts=Contacts(emails=["info@firma.ru"]),
        enrichment=Enrichment(status="ACTIVE", revenue=50_000_000, employee_count=30),
    )
    score, tier = outreach_score(hot)
    assert tier == "A" and score >= 70

    cold = _lead(outdated_score=20, contacts=Contacts())  # старый но без контактов
    s2, t2 = outreach_score(cold)
    assert t2 == "C" and s2 < score


def test_annotate_sets_fields_and_flags_corporate():
    leads = [_lead(contacts=Contacts(emails=["info@firma.ru"]))]
    annotate(leads)
    assert leads[0].outreach_tier in ("A", "B", "C")
    assert leads[0].corporate_email is True
    assert leads[0].outreach_score > 0


def test_summarize_counts():
    leads = [
        _lead(contacts=Contacts(emails=["info@firma.ru"]), source_query="стоматология Казань"),
        _lead(domain="two.ru", url="https://two.ru",
              contacts=Contacts(phones=["+7 900 000-00-00"]), source_query="стоматология Казань",
              enrichment=Enrichment(status="ACTIVE", revenue=5_000_000)),
    ]
    annotate(leads)
    s = summarize(leads)
    assert s["total"] == 2
    assert s["corporate_email"] == 1
    assert s["with_phone"] == 1
    assert s["with_revenue"] == 1
    assert s["active"] == 1
    assert s["top_categories"][0] == ("стоматология Казань", 2)
    assert s["tier_a"] + s["tier_b"] + s["tier_c"] == 2
