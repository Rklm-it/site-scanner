"""Содержимое старого сайта для брифа на прототип."""

from scanner import content

PAGE = '''<html><head>
<meta name="description" content="Изготовление металлоконструкций с 1998 года.">
<meta property="og:image" content="/img/cex.jpg">
</head><body>
<nav><a href="/">Главная</a><a href="/navesy">Навесы и козырьки</a>
<a href="/angary">Ангары и склады</a><a href="/contacts">Контакты</a>
<a href="tel:+78632632007">+7 863 263-20-07</a><a href="/m">info@firma.ru</a></nav>
<h1>Металлоконструкции любой сложности</h1><h2>Собственный цех</h2>
<img src="/img/logo.png"><img src="/img/angar-1.jpg">
<img src="data:image/gif;base64,R0lGOD"><img src="/img/sprite.svg">
</body></html>'''


def test_menu_is_services_without_service_links():
    c = content.extract(PAGE, base_url="https://firma.ru")
    assert c.menu == ["Навесы и козырьки", "Ангары и склады"]
    # «Главная»/«Контакты» — не услуги, телефон и почта — не разделы
    assert not any("Главн" in m or "Контакт" in m or "+7" in m or "@" in m for m in c.menu)


def test_headings_and_description():
    c = content.extract(PAGE, base_url="https://firma.ru")
    assert c.headings == ["Металлоконструкции любой сложности", "Собственный цех"]
    assert c.description.startswith("Изготовление металлоконструкций")


def test_images_absolute_without_service_graphics():
    """Логотипы, спрайты и data:-заглушки — не иллюстрации для прототипа."""
    c = content.extract(PAGE, base_url="https://firma.ru")
    assert c.images == ["https://firma.ru/img/cex.jpg",      # og:image первой
                        "https://firma.ru/img/angar-1.jpg"]
    assert not any("logo" in u or "sprite" in u or u.startswith("data:") for u in c.images)


def test_empty_page():
    c = content.extract("<html><body>ничего</body></html>", base_url="https://x.ru")
    assert c.is_empty


def test_brief_uses_real_content_not_invented():
    """Прототип показывают владельцу компании: услуги должны быть его,
    а не «средние по нише», которые придумает генератор."""
    from scanner import outreach
    from scanner.models import Lead

    lead = Lead(url="https://firma.ru", domain="firma.ru", source_query="металлоконструкции")
    lead.content = content.extract(PAGE, base_url="https://firma.ru")
    brief = outreach.build_lovable_brief(lead)

    assert "Навесы и козырьки" in brief and "Ангары и склады" in brief
    assert "https://firma.ru/img/angar-1.jpg" in brief
    assert "ничего не выдумывай" in brief
    assert "заменить на настоящие" in brief      # отзывы помечены как примеры


def test_brief_survives_empty_content():
    from scanner import outreach
    from scanner.models import Lead

    brief = outreach.build_lovable_brief(Lead(url="https://x.ru", domain="x.ru"))
    assert "Сделай современный одностраничный сайт" in brief
