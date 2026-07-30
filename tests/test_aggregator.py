"""Тесты отсева агрегаторов/каталогов."""

from scanner import aggregator


def test_detects_bank_directory():
    r = aggregator.aggregator_reason(title="Все банки России — адреса отделений и сайты")
    assert r and "все банки" in r


def test_detects_classifieds_board():
    r = aggregator.aggregator_reason(company="Доска бесплатных объявлений — КупиПродай")
    assert r is not None


def test_detects_via_meta_description():
    html = '<meta name="description" content="Каталог организаций и предприятий города">'
    assert aggregator.aggregator_reason(html=html) is not None


def test_real_business_not_flagged():
    assert aggregator.aggregator_reason(
        title="Стоматология Улыбка — лечение зубов в Казани", company="ООО Улыбка") is None
    # интернет-магазин с «каталогом товаров» — живой клиент, не агрегатор
    assert aggregator.aggregator_reason(title="Мебель на заказ — каталог товаров") is None
