"""Генерация письма-предложения под конкретный лид.

Из сигналов устаревания собирается персонализированный текст: упоминаются
реальные проблемы сайта, чтобы письмо не выглядело шаблонным.
"""

from __future__ import annotations

from .models import Lead

# сигнал (подстрока) -> человеческая формулировка проблемы
_SIGNAL_PHRASES: list[tuple[str, str]] = [
    ("viewport", "сайт не адаптирован под смартфоны — с телефона им пользоваться неудобно"),
    ("битый SSL", "просрочен сертификат безопасности — браузер показывает посетителям предупреждение"),
    ("нет HTTPS", "нет защищённого соединения (HTTPS) — браузеры помечают сайт как небезопасный"),
    ("Flash", "используется Flash, который уже не работает в современных браузерах"),
    ("вёрстка на таблицах", "устаревшая вёрстка"),
    ("устаревшие теги", "устаревшая вёрстка"),
    ("копирайт устарел", "дизайн заметно устарел"),
    ("устаревшая CMS", "сайт на устаревшей CMS"),
    ("старый jQuery", "используются устаревшие технологии"),
]

SIGNATURE = "[Ваше имя], веб-студия\n[телефон / телеграм]"


def _problem_phrases(signals: list[str], limit: int = 3) -> list[str]:
    phrases: list[str] = []
    for signal in signals:
        for needle, phrase in _SIGNAL_PHRASES:
            if needle.lower() in signal.lower() and phrase not in phrases:
                phrases.append(phrase)
    return phrases[:limit]


def build_message(lead: Lead, *, signature: str = SIGNATURE) -> dict[str, str]:
    """Возвращает {'pitch_subject', 'pitch_body'} — готовое письмо под лид."""
    company = lead.enrichment.official_name or lead.contacts.company or lead.domain
    name = (company or lead.domain).strip()

    phrases = _problem_phrases(lead.signals)
    if phrases:
        problems = phrases[0] if len(phrases) == 1 else \
            "; ".join(phrases[:-1]) + " и " + phrases[-1]
        problems_sentence = f"обратил внимание: {problems}."
    else:
        problems_sentence = "он выглядит заметно устаревшим."

    subject = f"Обновление сайта — {name}"

    body = (
        f"Здравствуйте!\n\n"
        f"Смотрел ваш сайт {lead.domain} и {problems_sentence} "
        f"Из-за этого часть клиентов, которые ищут вас в интернете, "
        f"уходит к конкурентам с более современными сайтами.\n\n"
        f"Мы делаем сайты под ключ — адаптивные под телефоны, быстрые, с онлайн-заявкой. "
        f"Могу показать примеры работ в вашей нише и бесплатно набросать, "
        f"как мог бы выглядеть ваш новый сайт.\n\n"
        f"Подскажите, пожалуйста, с кем можно обсудить обновление сайта?\n\n"
        f"С уважением,\n{signature}"
    )
    return {"pitch_subject": subject, "pitch_body": body}
