from scanner.validators import validate_inn, validate_ogrn


def test_valid_inn():
    assert validate_inn("7707083893")      # Сбербанк, 10 знаков
    assert validate_inn("500100732259")    # 12 знаков (физлицо/ИП)


def test_invalid_inn():
    assert not validate_inn("1234567890")
    assert not validate_inn("7707083894")  # испорчена контрольная цифра
    assert not validate_inn("770708389")   # мало цифр
    assert not validate_inn("abc")
    assert not validate_inn("")


def test_valid_ogrn():
    assert validate_ogrn("1027700132195")   # 13 знаков
    assert validate_ogrn("304500116000157")  # 15 знаков (ОГРНИП)


def test_invalid_ogrn():
    assert not validate_ogrn("1027700132190")  # испорчена контрольная
    assert not validate_ogrn("123")
    assert not validate_ogrn("")
