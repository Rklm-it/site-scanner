from scanner.outreach import build_message, _problem_phrases
from scanner.models import Lead, Contacts, Enrichment


def test_problem_phrases_from_signals():
    signals = ["нет meta viewport (не адаптивный)", "нет HTTPS", "нет favicon"]
    phrases = _problem_phrases(signals)
    assert any("смартфон" in p for p in phrases)
    assert any("HTTPS" in p for p in phrases)
    assert len(phrases) <= 3


def test_build_message_personalized():
    lead = Lead(
        url="https://stoma.ru", domain="stoma.ru",
        signals=["нет meta viewport (не адаптивный)", "битый SSL-сертификат"],
        enrichment=Enrichment(official_name="ООО Улыбка"),
    )
    msg = build_message(lead)
    assert "ООО Улыбка" in msg["pitch_subject"]
    assert "stoma.ru" in msg["pitch_body"]
    assert "смартфон" in msg["pitch_body"]           # сигнал viewport попал в текст
    assert "сертификат" in msg["pitch_body"]         # сигнал SSL попал в текст
    assert msg["pitch_body"].startswith("Здравствуйте")


def test_build_message_without_signals_has_fallback():
    lead = Lead(url="https://x.ru", domain="x.ru", contacts=Contacts(company="Фирма"))
    msg = build_message(lead)
    assert "устаревш" in msg["pitch_body"]
    assert "Фирма" in msg["pitch_subject"]
