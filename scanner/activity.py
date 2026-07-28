"""Детект признаков «живого бизнеса, который вкладывается в клиентов».

Аналитика, рекламные пиксели и виджеты захвата лидов = бизнес тратит
деньги на привлечение. Такой охотнее купит и новый сайт: у него есть
бюджет и он борется за клиента. Это сильный сигнал приоритета для аутрича
(в отличие от «просто старого» сайта, который могли забросить).
"""

from __future__ import annotations

# подстрока в HTML -> человекочитаемый инструмент
_MARKERS: list[tuple[str, str]] = [
    ("mc.yandex.ru", "Яндекс.Метрика"),
    ("metrika/tag", "Яндекс.Метрика"),
    ("ym(", "Яндекс.Метрика"),
    ("googletagmanager.com", "Google Tag Manager"),
    ("google-analytics.com", "Google Analytics"),
    ("gtag(", "Google Analytics"),
    ("an.yandex.ru", "Яндекс.Директ (реклама)"),
    ("googleadservices", "Google Ads (реклама)"),
    ("googlesyndication", "Google Ads (реклама)"),
    ("vk.com/rtrg", "ретаргетинг ВК"),
    ("top-fwz1.mail.ru", "top.mail.ru"),
    ("jivosite", "онлайн-чат Jivo"),
    ("jivo.chat", "онлайн-чат Jivo"),
    ("bitrix24", "виджет Битрикс24"),
    ("talk-me", "онлайн-чат Talk-Me"),
    ("callibri", "коллтрекинг Callibri"),
    ("callbackhunter", "обратный звонок"),
    ("envybox", "виджеты EnvyBox"),
    ("verbox", "онлайн-чат Verbox"),
    ("flexbe", "квиз/лендинг Flexbe"),
    ("marquiz", "квиз Marquiz"),
]


def detect(html: str) -> list[str]:
    """Возвращает список найденных маркетинговых инструментов (без дублей)."""
    if not html:
        return []
    low = html.lower()
    found: list[str] = []
    for needle, label in _MARKERS:
        if needle in low and label not in found:
            found.append(label)
    return found
