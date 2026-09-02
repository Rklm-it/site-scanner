#!/bin/bash
# Ищет в сайте признаки, по которым видно, что страницу собрала нейросеть.
# Делится на два уровня: «стоп» — показывать нельзя (чужие фото, чужие
# телефоны, английские кнопки, рыба), и «шаблон» — так делает любая модель,
# и клиент это уже видел у конкурентов.
# Выход 1 — есть «стоп». Шаблонность выход не меняет: это к дизайнеру, не к grep.
set -uo pipefail
export LC_ALL=C.UTF-8

TARGET="${1:-.}"
[ -e "$TARGET" ] || { echo "нет такого пути: $TARGET" >&2; exit 2; }

STOP=0
INC=(--include='*.html' --include='*.js' --include='*.mjs' --include='*.jsx'
     --include='*.ts' --include='*.tsx' --include='*.css' --include='*.vue'
     --include='*.json')

# awk и cut режут по байтам и рвут многобайтные символы; питон в проекте есть всегда
trunc() { python3 -c "
import sys
for line in sys.stdin:
    print(line.rstrip()[:150])"; }

# grep запускается из каталога цели, чтобы в выводе были короткие пути
scan() {
  if [ -d "$TARGET" ]; then (cd "$TARGET" && grep -rniE "$1" . "${INC[@]}" 2>/dev/null) | trunc
  else grep -niE "$1" "$TARGET" 2>/dev/null | trunc; fi
}
count() { scan "$1" | wc -l | tr -d ' '; }

say() {  # say <уровень> <что> <чем чинить> <вывод>
  [ -z "$4" ] && return 0
  [ "$1" = стоп ] && STOP=1
  printf '\n[%s] %s\n      → %s\n' "$1" "$2" "$3"
  printf '%s\n' "$4" | head -4 | sed 's/^/      /'
}

echo "=== Чужое и недоделанное (показывать нельзя) ==="

say стоп "фотографии со стока по прямой ссылке" \
  "поставить фото клиента из выгрузки; чужие стоки узнают, и на них нет прав" \
  "$(scan 'images\.unsplash\.com|source\.unsplash|pexels\.com|placehold\.co|via\.placeholder|picsum\.photos')"

say стоп "чужой или выдуманный контакт" \
  "телефон, почта и адрес — из карточки клиента, больше ниоткуда" \
  "$(scan '\+1[ (-]|555-01|example\.(com|org)|@example|your-?(company|domain)|john\.?doe')"

say стоп "рыба вместо текста" \
  "текст из выгрузки старого сайта; чего нет — заглушка в квадратных скобках" \
  "$(scan 'lorem ipsum|dolor sit amet|текст-?рыба|ваш текст здесь')"

say стоп "английская кнопка или подпись на русском сайте" \
  "перевести; в промпте прямо просить русские подписи" \
  "$(scan '>(get started|learn more|read more|contact us|our services|about us|sign up|book now)<')"

say стоп "выдуманная цифра доверия" \
  "убрать или подтвердить у клиента: цифру спросят на первой же встрече" \
  "$(scan '(10,?000\+|1000\+|500\+) (companies|clients|customers|users)|trusted by|более (100|500|1000) (компаний|клиентов)')"

echo
echo "=== Шаблон: так делает любая модель ==="

say шаблон "градиентный текст заголовка" \
  "убрать; в 2019 это было приёмом, сейчас это подпись нейросети" \
  "$(scan 'bg-clip-text[^"]*text-transparent|text-transparent[^"]*bg-clip-text|-webkit-background-clip: *text')"

say шаблон "фиолетово-розовый градиент" \
  "взять палитру клиента: цвета его продукции, спецодежды, вывески" \
  "$(scan 'from-(purple|violet|indigo|fuchsia)-[0-9]+ to-(pink|rose|fuchsia|purple)-[0-9]+|linear-gradient\([^)]*(#8b5cf6|#a855f7|#d946ef|#ec4899)')"

say шаблон "кремовый фон с терракотой — дефолтная палитра моделей" \
  "см. три запрещённых вида во /frontend-design" \
  "$(scan '#f4f1ea|#faf7f2|#fdfaf5|#e07a5f|#c1440e')"

say шаблон "нумерация 01 / 02 / 03 у секций" \
  "оставить, только если это правда последовательность — этапы работы, срок" \
  "$(scan '>0[1-9]<|"0[1-9]"[,)]| 0[1-9] / 0[1-9]')"

say шаблон "эмодзи вместо иконок" \
  "иконки из набора или ничего; эмодзи в корпоративном блоке читаются как черновик" \
  "$(scan '(🚀|✨|💡|🎯|⚡|🔥|💪|🌟|✅|📈|🛠️|🏆)')"

EYE=$(count 'uppercase[^"]*tracking-(wide|wider|widest)|tracking-(wide|wider|widest)[^"]*uppercase')
if [ "$EYE" -ge 3 ]; then
  printf '\n[шаблон] мелкий надзаголовок над каждой секцией (%s шт.)\n' "$EYE"
  printf '      → оставить один-два; когда он над каждой секцией, ритм становится механическим\n'
fi

ROUND=$(count 'rounded-2xl|rounded-3xl'); SHAD=$(count 'shadow-(lg|xl|2xl)')
if [ "$ROUND" -ge 8 ] && [ "$SHAD" -ge 8 ]; then
  printf '\n[шаблон] всё в карточках с одним радиусом и тенью (%s радиусов, %s теней)\n' "$ROUND" "$SHAD"
  printf '      → часть блоков без карточки: текст на фоне, таблица, полоса во всю ширину\n'
fi

# Кроме самих font-family подаём и объявления пользовательских свойств:
# шрифт сплошь и рядом задан как `--zag:'Unbounded',…`, а в правиле стоит
# `font-family:var(--zag)`. Без этих строк проверка видит один var() и
# докладывает «шрифт только системный» на странице с двумя своими шрифтами.
scan 'font-family|--[a-z0-9_-]+ *:' | python3 "$(dirname "$0")/_fonts.py"

echo
if [ "$STOP" -eq 1 ]; then
  echo "Показывать нельзя: наверху есть «стоп»."
  echo "Чужие фото и чужие телефоны — это не шаблонность, это ошибка в работе."
  exit 1
fi
echo "«Стоп» не нашлось. Шаблонность grep-ом не закрывается: прогони страницу"
echo "по каталогу в web-design-engineer/references/failure-patterns.md."
exit 0
