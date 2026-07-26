from scanner.contacts import extract, _clean_phone

PAGE = """<html><head>
<title>ООО Ромашка — доставка воды | Казань</title>
<meta property="og:site_name" content="Ромашка">
</head><body>
<a href="mailto:info@romashka.ru">почта</a>
Пишите на sales@romashka.ru
<a href="tel:+78435551234">Позвонить</a>
Телефон: 8 (843) 555-77-88
<a href="https://vk.com/romashka">ВК</a>
<a href="https://t.me/romashka_bot">Telegram</a>
<a href="/contacts">Контакты</a>
ИНН 1655123456 ОГРН 1021602812345
</body></html>"""


def test_emails_extracted():
    c = extract(PAGE, base_url="https://romashka.ru")
    assert "info@romashka.ru" in c.emails
    assert "sales@romashka.ru" in c.emails


def test_phones_normalized():
    c = extract(PAGE, base_url="https://romashka.ru")
    assert any(p.startswith("+7 843") for p in c.phones)


def test_socials_and_requisites():
    c = extract(PAGE, base_url="https://romashka.ru", title="ООО Ромашка")
    assert any("vk.com" in s for s in c.socials)
    assert any("t.me" in s for s in c.socials)
    assert c.inn == "1655123456"
    assert c.ogrn == "1021602812345"
    assert c.company == "Ромашка"
    assert c.contact_page and c.contact_page.endswith("/contacts")


def test_clean_phone():
    assert _clean_phone("8 (843) 555-77-88") == "+7 843 555-77-88"
    assert _clean_phone("+7 843 555 12 34") == "+7 843 555-12-34"
