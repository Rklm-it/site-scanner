"""Читает со stdin строки с font-family и говорит, есть ли среди них свой шрифт.

Построчным grep это не проверить: строка со своим шрифтом почти всегда
заканчивается запасным `serif`, и по этому слову её принимали за системную.

Второй случай, на котором проверка врала: шрифт объявлен пользовательским
свойством (`--zag:'Unbounded',sans-serif`), а в правиле стоит
`font-family:var(--zag)`. Токен `var(...)` пропускался, своих имён не
находилось, и страница с двумя фирменными шрифтами получала «шрифт только
системный». Поэтому теперь: запоминаем, какие переменные использованы как
font-family, и разбираем их объявления как шрифтовые стеки. Именно
использованные — иначе в шрифты попадёт первая же переменная с текстовым
значением.
"""
import re
import sys

GENERIC = {
    'inter', 'system-ui', 'ui-sans-serif', 'ui-serif', 'ui-monospace',
    'sans-serif', 'serif', 'monospace', 'cursive', 'fantasy',
    '-apple-system', 'blinkmacsystemfont', 'segoe ui', 'roboto', 'helvetica',
    'helvetica neue', 'arial', 'apple color emoji', 'segoe ui emoji',
    'noto color emoji', 'inherit', 'initial', 'unset',
}

def imena(stek: str) -> set:
    """Шрифтовой стек -> имена, которые не являются системными."""
    out = set()
    for token in stek.split(','):
        token = token.strip().strip('\'"\\').lower()
        if token and token not in GENERIC and not token.startswith('var('):
            out.add(token)
    return out


named = set()
peremennye = {}          # --имя -> объявленный стек
nuzhny = set()           # какие переменные реально стоят в font-family
seen = False
for line in sys.stdin:
    for decl in re.findall(r'font-family\s*:\s*([^;{}]+)', line, re.I):
        seen = True
        named |= imena(decl)
        nuzhny |= set(re.findall(r'var\(\s*(--[a-z0-9_-]+)', decl, re.I))
    for imya, znachenie in re.findall(r'(--[a-z0-9_-]+)\s*:\s*([^;{}]+)', line, re.I):
        peremennye[imya.lower()] = znachenie

for imya in nuzhny:
    named |= imena(peremennye.get(imya.lower(), ''))

if seen and not named:
    print('\n[шаблон] шрифт только системный или Inter')
    print('      → пара «характерный заголовочный + спокойный текстовый», '
          'см. /frontend-design')
