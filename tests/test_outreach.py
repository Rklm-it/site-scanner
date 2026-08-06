from scanner.outreach import (build_message, build_call_script, build_talking_points,
                              build_lovable_brief, _pick_hook)
from scanner.models import Lead, Contacts, Enrichment


def test_lovable_brief_personalized():
    lead = Lead(url="https://stoma.ru", domain="stoma.ru", source_query="стоматология Батайск",
                signals=["нет meta viewport (не адаптивный)", "нет HTTPS"],
                contacts=Contacts(phones=["+7 900 000-00-00"], emails=["a@stoma.ru"]),
                enrichment=Enrichment(official_name="ООО Улыбка"))
    brief = build_lovable_brief(lead)
    assert "ООО Улыбка" in brief and "стоматология Батайск" in brief
    assert "stoma.ru" in brief                       # ссылка на старый сайт
    assert "+7 900 000-00-00" in brief               # контакты в брифе
    assert "бело-голубой" in brief                   # стиль подобран под нишу
    assert "Форма заявки" in brief


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


# --------------------------------------------------------------------------- #
# Блок «кто мы»: единый для писем и звонков, правится в настройках
# --------------------------------------------------------------------------- #
from scanner import outreach  # noqa: E402
def _lead_for_about():
    from scanner.models import Lead

    l = Lead(url="https://firma.ru", domain="firma.ru")
    l.signals = ["нет meta viewport (не адаптивный)"]
    return l


def test_about_lands_in_email_and_call(monkeypatch):
    monkeypatch.delenv("STUDIO_ABOUT", raising=False)
    lead = _lead_for_about()
    body = outreach.build_message(lead, about="Нас четверо, я веду проект.")["pitch_body"]
    script = outreach.build_call_script(lead, about="Нас четверо, я веду проект.")
    assert "Нас четверо, я веду проект." in body
    assert "Нас четверо, я веду проект." in script


def test_about_falls_back_to_settings_then_default(monkeypatch):
    lead = _lead_for_about()

    monkeypatch.setenv("STUDIO_ABOUT", "Из настроек.")
    assert "Из настроек." in outreach.build_message(lead)["pitch_body"]

    monkeypatch.delenv("STUDIO_ABOUT", raising=False)
    assert outreach.DEFAULT_ABOUT in outreach.build_message(lead)["pitch_body"]

    monkeypatch.setenv("STUDIO_ABOUT", "   ")          # пробелы = не задано
    assert outreach.DEFAULT_ABOUT in outreach.build_message(lead)["pitch_body"]


def test_call_script_answers_team_questions(monkeypatch):
    monkeypatch.delenv("STUDIO_ABOUT", raising=False)
    script = outreach.build_call_script(_lead_for_about())
    for q in ("портфолио", "Кто конкретно будет делать", "пропадёте с деньгами",
              "Почему так дёшево"):
        assert q in script, q


def test_default_about_claims_nothing_unverifiable():
    """В формулировке по умолчанию нет выдуманного стажа и чужих кейсов —
    такое проверяется за пять минут и хоронит сделку."""
    low = outreach.DEFAULT_ABOUT.lower()
    for bad in ("лет на рынке", "сделали", "более ", "крупнейш", "№1", "лидер"):
        assert bad not in low, bad
