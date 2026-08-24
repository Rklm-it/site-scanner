"""Читает со stdin строки с font-family и говорит, есть ли среди них свой шрифт.

Построчным grep это не проверить: строка со своим шрифтом почти всегда
заканчивается запасным `serif`, и по этому слову её принимали за системную.
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

named = set()
seen = False
for line in sys.stdin:
    for decl in re.findall(r'font-family\s*:\s*([^;{}]+)', line, re.I):
        seen = True
        for token in decl.split(','):
            token = token.strip().strip('\'"\\').lower()
            if token and token not in GENERIC and not token.startswith('var('):
                named.add(token)

if seen and not named:
    print('\n[шаблон] шрифт только системный или Inter')
    print('      → пара «характерный заголовочный + спокойный текстовый», '
          'см. /frontend-design')
