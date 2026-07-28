from scanner.outreach import build_message, _pick_hook
from scanner.models import Lead, Contacts, Enrichment


def test_pick_hook_prioritizes_mobile():
    # из нескольких проблем выбирается ОДНА, самая приоритетная (мобильная)
    hook = _pick_hook(["нет HTTPS", "нет meta viewport (не адаптивный)", "битый SSL-сертификат"])
    assert "телефон" in hook


def test_pick_hook_fallback_without_signals():
    assert "устаревш" in _pick_hook([])


def test_build_message_short_and_personalized():
    lead = Lead(
        url="https://stoma.ru", domain="stoma.ru",
        signals=["нет meta viewport (не адаптивный)", "битый SSL-сертификат"],
        enrichment=Enrichment(official_name="ООО Улыбка"),
    )
    msg = build_message(lead)
    assert msg["pitch_subject"] == "По сайту ООО Улыбка"
    body = msg["pitch_body"]
    assert body.startswith("Здравствуйте")
    assert "stoma.ru" in body
    assert "телефон" in body                 # выбрана мобильная зацепка
    assert "сертификат" not in body          # вторую проблему не тащим — письмо короткое
    assert "бесплатно" in body               # ценность вперёд
    assert "P.S." in body and "не побеспокою" in body  # строчка-отписка
    assert len(body.split()) < 110           # держим письмо коротким


def test_build_message_uses_custom_signature():
    lead = Lead(url="https://x.ru", domain="x.ru", contacts=Contacts(company="Фирма"),
                signals=["нет HTTPS"])
    msg = build_message(lead, signature="Иван Петров\n+7 999 111-22-33\nhttps://portfolio.ru")
    assert "Иван Петров" in msg["pitch_body"]
    assert "https://portfolio.ru" in msg["pitch_body"]
    assert "[Ваше имя]" not in msg["pitch_body"]
