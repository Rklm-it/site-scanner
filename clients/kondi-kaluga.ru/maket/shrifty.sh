#!/usr/bin/env bash
# Пересобирает shrifty.css и fonts/ под то, что реально осталось в index.html.
#
# Зачем отдельно от sobrat.js: тут нужна сеть, а сборку страницы хочется
# гонять без неё. Запускать после каждой правки набора иконок — иначе
# на экране вместо иконки стоит слово (DOMAIN, DIRECTIONS_CAR: уже ловили).
#
#   ./shrifty.sh          — из каталога maket, index.html должен быть собран
set -e
cd "$(dirname "$0")/site"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

IKONKI=$(grep -oP '(?<=material-symbols-outlined)[^>]*>\K[a-z_]+(?=</span>)' index.html \
         | sort -u | paste -sd,)
echo "иконок в странице: $(echo "$IKONKI" | tr ',' '\n' | wc -l) — $IKONKI"

mkdir -p fonts
curl -sS --max-time 40 -A "$UA" -o /tmp/manrope.css \
  "https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap"
# Знака рубля в Manrope нет ни в одном подмножестве Google (в кириллическом
# лежит гривна, U+20B4, а не U+20BD), и ₽ рисовался системным шрифтом — на
# странице, где цены и есть главное, это видно. Берём один глиф из Inter и
# подсовываем его под именем Manrope через unicode-range: 2,2 КБ.
curl -sS --max-time 40 -A "$UA" -o /tmp/rubl.css \
  "https://fonts.googleapis.com/css2?family=Inter:wght@400..800&text=%E2%82%BD"
curl -sS --max-time 40 -A "$UA" -o /tmp/ms.css \
  "https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0&icon_names=$IKONKI&display=block"

python3 - <<'PY'
import re, os, subprocess
css = open('/tmp/manrope.css', encoding='utf-8').read()
out, vzyato = [], set()
for name, body in re.findall(r'/\* ([\w-]+) \*/\s*@font-face \{(.*?)\}', css, re.S):
    if name not in ('cyrillic', 'latin') or name in vzyato:
        continue
    vzyato.add(name)
    url = re.search(r'url\((\S+?)\)', body).group(1)
    rng = re.search(r'unicode-range: ([^;]+);', body).group(1)
    fn = f'manrope-{name}.woff2'
    subprocess.run(['curl', '-sS', '--max-time', '40', '-o', f'fonts/{fn}', url], check=True)
    out.append(f"@font-face{{font-family:'Manrope';font-style:normal;font-weight:400 800;"
               f"font-display:swap;src:url(fonts/{fn}) format('woff2');unicode-range:{rng};}}")
# Manrope — переменный шрифт, Google отдаёт один файл на подмножество, а не на
# начертание: качать пять раз одно и то же незачем.
rubl = open('/tmp/rubl.css', encoding='utf-8').read()
url = re.search(r'url\((\S+?)\)', rubl).group(1)
subprocess.run(['curl', '-sS', '--max-time', '40', '-o', 'fonts/rubl.woff2', url], check=True)
out.append("@font-face{font-family:'Manrope';font-style:normal;font-weight:400 800;"
           "font-display:swap;src:url(fonts/rubl.woff2) format('woff2');unicode-range:U+20BD;}")

ms = open('/tmp/ms.css', encoding='utf-8').read()
url = re.search(r'url\((\S+?)\)', ms).group(1)
subprocess.run(['curl', '-sS', '--max-time', '40', '-o', 'fonts/material-symbols.woff2', url], check=True)
out.append("@font-face{font-family:'Material Symbols Outlined';font-style:normal;font-weight:400;"
           "font-display:block;src:url(fonts/material-symbols.woff2) format('woff2');}")
# font-display: block — браузер держит иконки невидимыми, пока шрифт не пришёл,
# и слова-лигатуры (call, person) на экран не попадают.
out.append(".material-symbols-outlined{font-family:'Material Symbols Outlined';font-weight:normal;"
           "font-style:normal;font-size:24px;line-height:1;letter-spacing:normal;text-transform:none;"
           "display:inline-block;white-space:nowrap;word-wrap:normal;direction:ltr;"
           "-webkit-font-feature-settings:'liga';-webkit-font-smoothing:antialiased;}")
open('shrifty.css', 'w', encoding='utf-8').write('\n'.join(out) + '\n')
PY
du -sh fonts
