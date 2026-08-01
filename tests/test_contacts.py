from scanner.contacts import extract, _clean_phone, _deobfuscate

PAGE = """<html><head>
<title>ООО Ромашка — доставка воды | Казань</title>
<meta property="og:site_name" content="Ромашка">
</head><body>
<a href="mailto:info@romashka.ru">почта</a>
Пишите на sales@romashka.ru
<a href="tel:+78435551234">Позвонить</a>
Телефон: 8 (843) 555-77-88, а также 8-800-555-35-35
<a href="https://vk.com/romashka">ВК</a>
<a href="https://t.me/romashka_bot">Telegram</a>
<a href="/contacts">Контакты</a>
ИНН 7707083893 ОГРН 1027700132195
</body></html>"""


def test_emails_extracted():
    c = extract(PAGE, base_url="https://romashka.ru")
    assert "info@romashka.ru" in c.emails
    assert "sales@romashka.ru" in c.emails


def test_phones_normalized():
    c = extract(PAGE, base_url="https://romashka.ru")
    assert any(p.startswith("+7 843") for p in c.phones)
    assert any("800" in p for p in c.phones)  # 8-800 тоже пойман


def test_socials_and_valid_requisites():
    c = extract(PAGE, base_url="https://romashka.ru", title="ООО Ромашка")
    assert any("vk.com" in s for s in c.socials)
    assert any("t.me" in s for s in c.socials)
    assert c.inn == "7707083893"        # прошёл контрольную сумму
    assert c.ogrn == "1027700132195"
    assert c.company == "Ромашка"
    assert c.contact_page and c.contact_page.endswith("/contacts")


def test_invalid_inn_rejected():
    page = "<html><body>ИНН 1234567890 текст</body></html>"
    c = extract(page, base_url="https://x.ru")
    assert c.inn is None  # контрольная сумма не сходится — не берём


def test_inn_extracted_across_tags():
    # метка и число в соседних тегах — частый случай в подвале сайта
    page = ("<html><body><footer><span>ИНН:</span>"
            "<span>7707083893</span></footer></body></html>")
    c = extract(page, base_url="https://x.ru")
    assert c.inn == "7707083893"


def test_email_deobfuscation():
    assert _deobfuscate("info (at) romashka точка ru") == "info@romashka.ru"
    page = "<html><body>Почта: info (at) romashka точка ru</body></html>"
    c = extract(page, base_url="https://romashka.ru")
    assert "info@romashka.ru" in c.emails


def test_deobfuscation_does_not_touch_words():
    # «at»/«dot» внутри слов не должны становиться @/. (регресс на мусор из JS)
    assert _deobfuscate("window.location.replace") == "window.location.replace"
    js = ("<html><body><script>window.location.replace('/x');"
          "var f='vksansdisplaylightlatin.v320.woff';</script></body></html>")
    c = extract(js, base_url="https://site.ru")
    assert c.emails == []


def test_clean_phone():
    assert _clean_phone("8 (843) 555-77-88") == "+7 843 555-77-88"
    assert _clean_phone("+7 843 555 12 34") == "+7 843 555-12-34"


def test_inn_in_paired_footer_formats():
    """«ИНН/КПП 7707083893/770701001» и родня — самая частая запись реквизитов
    в подвале. Раньше все эти варианты пролетали, и лид оставался без оборота."""
    from scanner.contacts import extract

    variants = [
        "ИНН/КПП 7707083893/770701001",
        "ИНН / КПП: 7707083893 / 770701001",
        "ИНН — 7707083893",
        "ИНН №7707083893",
        "ОГРН/ИНН 1027700132195 / 7707083893",
    ]
    for v in variants:
        c = extract(f"<html><body><p>{v}</p></body></html>", base_url="https://x.ru")
        assert c.inn == "7707083893", v


def test_ogrn_in_paired_footer_format():
    from scanner.contacts import extract

    c = extract("<html><body>ИНН/ОГРН 7707083893 / 1027700132195</body></html>",
                base_url="https://x.ru")
    assert c.ogrn == "1027700132195"


def test_reqisites_do_not_capture_other_numbers():
    """Расчётный счёт, БИК и ОКПО не должны попадать в ИНН."""
    from scanner.contacts import extract

    c = extract("<html><body>р/с 40702810900000012345 БИК 044525225 ОКПО 12345678"
                "</body></html>", base_url="https://x.ru")
    assert c.inn is None


# --------------------------------------------------------------------------- #
# Юрлицо из текста: по заголовку страницы реестр компанию не находит
# --------------------------------------------------------------------------- #
def test_legal_name_beats_page_title():
    """«Салон красоты "Крокус" в Ростове-на-Дону.» в реестре не ищется,
    а «ООО «Крокус»» из подвала — ищется."""
    from scanner.contacts import extract

    c = extract('<html><body>Салон красоты'
                '<footer>ООО «Крокус», г. Ростов-на-Дону</footer></body></html>',
                base_url="https://x.ru", title='Салон красоты "Крокус" в Ростове-на-Дону.')
    assert c.legal_name == "ООО «Крокус»"
    assert c.company == 'Салон красоты "Крокус" в Ростове-на-Дону.'   # для показа


def test_legal_name_keeps_abbreviation_prefix():
    """Между формой и названием бывает приставка: ООО ПКФ, ГУП РО, ЗАО НПО."""
    from scanner.contacts import find_legal_name

    assert find_legal_name('ООО ПКФ "НОВЫЙ КОЛОС"') == 'ООО ПКФ «НОВЫЙ КОЛОС»'
    assert find_legal_name('ГУП РО "Фармацевтический центр"') == 'ГУП РО «Фармацевтический центр»'


def test_legal_name_without_quotes_stops_at_sentence():
    """Без кавычек название не должно утягивать сказуемое из предложения."""
    from scanner.contacts import find_legal_name

    assert find_legal_name("Наша компания ЗАО Ростовский Завод работает с 1998") == \
        "ЗАО Ростовский Завод"
    assert find_legal_name("ГУП РО Фармацевтический центр — справочная") == \
        "ГУП РО Фармацевтический центр"


def test_legal_name_ip_and_absent():
    from scanner.contacts import find_legal_name

    assert find_legal_name("ИП Мкртичян Наталья Сергеевна, тел 8 918") == \
        "ИП Мкртичян Наталья Сергеевна"
    assert find_legal_name("ООО было создано как «филиал» в прошлом году") is None
    assert find_legal_name("обычный текст без юрлица") is None


def test_requisites_page_wins_over_contacts():
    """ИНН почти всегда на «Реквизитах». Раньше бралась первая попавшаяся
    ссылка, и бот уходил на «О нас», где ИНН нет."""
    from scanner.contacts import extract

    c = extract('<html><body><a href="/about">О нас</a>'
                '<a href="/contacts">Контакты</a><a href="/rekvizity">Реквизиты</a>'
                '</body></html>', base_url="https://x.ru")
    assert c.contact_page == "https://x.ru/rekvizity"
    assert c.extra_pages == ["https://x.ru/contacts", "https://x.ru/about"]
