from scanner.heuristics import analyze, _find_copyright_year, CURRENT_YEAR

OLD_PAGE = """<html>
<head><title>Стоматология Улыбка</title>
<meta name="generator" content="Joomla! 1.5">
</head>
<body bgcolor="#ffffff">
<table width="900"><tr><td>
<font size="3">Добро пожаловать</font>
<center>Наша клиника</center>
</td></tr></table>
<table width="900"><tr><td>контент</td></tr></table>
<table width="900"><tr><td>ещё</td></tr></table>
<embed src="intro.swf">
© 2009 Улыбка. Все права защищены.
</body></html>"""

MODERN_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
<title>Современная студия</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta property="og:title" content="Студия">
<meta property="og:image" content="/img/cover.jpg">
<link rel="icon" href="/favicon.ico">
<style>@media (max-width: 600px){body{font-size:14px}}</style>
</head>
<body><h1>Привет</h1><p>© YEAR Студия</p></body></html>""".replace("YEAR", str(CURRENT_YEAR))


def test_old_page_scores_high():
    h = analyze(OLD_PAGE, final_url="http://old.example")
    assert h.outdated_score >= 60, (h.outdated_score, h.signals)
    assert not h.mobile_friendly
    assert not h.https
    assert h.cms and "Joomla" in h.cms
    assert h.copyright_year == 2009
    joined = " ".join(h.signals)
    assert "viewport" in joined
    assert "Flash" in joined
    assert "устаревшие теги" in joined


def test_modern_page_scores_low():
    h = analyze(MODERN_PAGE, final_url="https://new.example")
    assert h.outdated_score <= 15, (h.outdated_score, h.signals)
    assert h.mobile_friendly
    assert h.https


def test_copyright_year_parsing():
    assert _find_copyright_year("© 2011 Компания") == 2011
    assert _find_copyright_year("Copyright 2008–2014 ООО") == 2014
    assert _find_copyright_year("нет года тут") is None


def test_https_flag_from_url():
    h = analyze("<html></html>", final_url="https://secure.example")
    assert h.https is True
    signals = " ".join(h.signals)
    assert "нет HTTPS" not in signals
