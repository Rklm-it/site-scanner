from scanner.activity import detect


def test_detect_metrika_and_analytics():
    html = "<script>ym(123,'init');</script><script src='https://mc.yandex.ru/metrika/tag.js'></script>"
    tools = detect(html)
    assert "Яндекс.Метрика" in tools
    assert tools.count("Яндекс.Метрика") == 1  # без дублей


def test_detect_chat_and_ads():
    html = "<script src='//code.jivosite.com/widget/x'></script><div>googleadservices.com/pagead</div>"
    tools = detect(html)
    assert any("Jivo" in t for t in tools)
    assert any("реклама" in t for t in tools)


def test_detect_empty():
    assert detect("<html><body>обычный старый сайт</body></html>") == []
    assert detect("") == []
