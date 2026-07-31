from scanner.outreach import build_message, build_call_script, build_talking_points, _pick_hook
from scanner.models import Lead, Contacts, Enrichment


def test_talking_points_two_registers():
    lead = Lead(url="https://x.ru", domain="x.ru",
                signals=["нет meta viewport (не адаптивный)", "нет HTTPS", "старый PHP (php/5.3.29)"])
    tp = build_talking_points(lead)
    assert tp["savvy"] and tp["simple"]
    # для шарящих — термины, для не шарящих — без них
    savvy_txt, simple_txt = " ".join(tp["savvy"]).lower(), " ".join(tp["simple"]).lower()
    assert "mobile-first" in savvy_txt or "ранжир" in savvy_txt
    assert "телефон" in simple_txt
    # обе версии заканчиваются оффером про готовый прототип
    assert any("набросок" in x for x in tp["savvy"])
    assert any("набросок" in x for x in tp["simple"])


def test_talking_points_fallback_without_signals():
    tp = build_talking_points(Lead(url="https://x.ru", domain="x.ru", signals=[]))
    assert len(tp["savvy"]) >= 1 and len(tp["simple"]) >= 1


def test_build_call_script():
    lead = Lead(url="https://stoma.ru", domain="stoma.ru",
                signals=["нет meta viewport (не адаптивный)"],
                enrichment=Enrichment(official_name="ООО Улыбка"))
    s = build_call_script(lead, caller_name="Иван")
    assert "Иван" in s
    assert "stoma.ru" in s
    assert "телефон" in s                 # зацепка про мобильную версию
    assert "возражени" in s.lower()       # блок ответов на возражения
    assert "Приветствие" in s


def test_call_script_uses_director_name():
    # ФИО руководителя из ЕГРЮЛ → обращение по имени-отчеству и проход через секретаря
    lead = Lead(url="https://stoma.ru", domain="stoma.ru",
                signals=["нет HTTPS"],
                enrichment=Enrichment(official_name="ООО Улыбка",
                                      management="Петров Сергей Иванович"))
    s = build_call_script(lead)
    assert "Сергей Иванович" in s          # обращаемся по имени-отчеству
    assert "Соедините" in s                # блок прохода через секретаря
    # без руководителя блока прохода нет
    plain = build_call_script(Lead(url="https://x.ru", domain="x.ru", signals=["нет HTTPS"]))
    assert "Соедините" not in plain
    assert plain.count("Здравствуйте")      # приветствие всё равно есть


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
