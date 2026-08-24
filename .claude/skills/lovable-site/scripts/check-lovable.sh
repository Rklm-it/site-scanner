#!/bin/bash
# Ищет следы Lovable в собранном прототипе. Пересборка возвращает их обратно,
# поэтому проверка идёт перед каждой выкладкой, а не один раз при заведении
# клиента. Выход 1 — нашлось, выкладывать нельзя.
set -uo pipefail

TARGET="${1:-.}"
[ -e "$TARGET" ] || { echo "нет такого пути: $TARGET" >&2; exit 2; }

FOUND=0
report() {  # report <что нашли> <как чинить> <вывод grep>
  [ -z "$3" ] && return 0
  FOUND=1
  printf '\n[!] %s\n    чинить: %s\n' "$1" "$2"
  printf '%s\n' "$3" | head -5 | sed 's/^/    /'
}

# --include не нужен: в бандле следы попадают и в .js, и в .json карт исходников
scan() { grep -rniE "$1" "$TARGET" \
    --include='*.html' --include='*.js' --include='*.mjs' \
    --include='*.json' --include='*.webmanifest' 2>/dev/null | cut -c1-160; }

report "скрипт конструктора" \
       "убрать <script src=\"https://cdn.gpteng.co/gptengineer.js\"> из index.html" \
       "$(scan 'gpteng|gptengineer')"

report "бейдж или упоминание Lovable" \
       "снять блок «Edit with Lovable» в правом нижнем углу и все упоминания в разметке" \
       "$(scan 'lovable')"

report "заголовок по умолчанию" \
       "поставить <title> с названием компании клиента" \
       "$(scan '<title>[^<]*(generated project|vite \+ react|lovable)')"

report "generator в мета-тегах" \
       "удалить <meta name=\"generator\">" \
       "$(scan '<meta[^>]+name=.generator')"

# og:image и twitter:image на чужом домене — картинка превью в мессенджерах
report "og:image или twitter:image ведёт не на сайт клиента" \
       "заменить на скриншот самого сайта, положенный рядом" \
       "$(scan '(og:image|twitter:image)[^>]*(lovable|gpteng|placehold)')"

if [ "$FOUND" -eq 0 ]; then
  echo "чисто: следов Lovable в $TARGET не нашлось"
  echo "остаётся глазами: favicon по умолчанию и og:image — открыть страницу и вкладку браузера"
  exit 0
fi

printf '\nВыкладывать нельзя. Клиент смотрит на сайт своей компании, а по бейджу\n'
printf 'за минуту выясняет, что сайт собран мышкой, — разговор о цене после\n'
printf 'этого другой.\n'
exit 1
