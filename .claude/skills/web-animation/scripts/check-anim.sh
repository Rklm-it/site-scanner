#!/bin/bash
# Смотрит, чем и как на сайте сделано движение. Два уровня, как в
# check-shablon.sh: «стоп» — выкладывать нельзя (тяжёлая 3D-библиотека, две
# библиотеки анимации разом, анимация на заголовке первого экрана, движение
# без prefers-reduced-motion), и «внимание» — так делать не надо, но решает
# человек. Выход 1 — есть «стоп».
#
# Скрипт читает текст, а не поведение: он ловит то, что видно грепом, и не
# заменяет просмотр страницы в браузере на узком экране.
set -uo pipefail
export LC_ALL=C.UTF-8

TARGET="${1:-.}"
[ -e "$TARGET" ] || { echo "нет такого пути: $TARGET" >&2; exit 2; }

STOP=0
INC=(--include='*.html' --include='*.js' --include='*.mjs' --include='*.jsx'
     --include='*.ts' --include='*.tsx' --include='*.css' --include='*.scss'
     --include='*.vue' --include='package.json')
EXC=(--exclude-dir=node_modules --exclude-dir=.git --exclude-dir=.next)

trunc() { python3 -c "
import sys
for line in sys.stdin:
    print(line.rstrip()[:150])"; }

scan() {
  if [ -d "$TARGET" ]; then (cd "$TARGET" && grep -rniE "$1" . "${INC[@]}" "${EXC[@]}" 2>/dev/null) | trunc
  else grep -niE "$1" "$TARGET" 2>/dev/null | trunc; fi
}
count() { scan "$1" | grep -c . | tr -d ' '; }

say() {  # say <уровень> <что> <чем чинить> <вывод>
  [ -z "$4" ] && return 0
  [ "$1" = стоп ] && STOP=1
  printf '\n[%s] %s\n      → %s\n' "$1" "$2" "$3"
  printf '%s\n' "$4" | head -4 | sed 's/^/      /'
}

echo "=== Цена движения (выкладывать нельзя) ==="

say стоп "3D-движок на сайте малого бизнеса" \
  "снять; мегабайты и греющийся телефон ради одного впечатления, платить будет выдача" \
  "$(scan '"(three|@react-three/fiber|@react-three/drei|@splinetool/[a-z-]+|vanta|pixi\.js|babylonjs)"|splinetool\.com|vanta\.(net|dots|waves)|new THREE\.')"

# Две библиотеки анимации в одном проекте — это два движка ради одного и того же.
libs=""
for pair in "gsap:GSAP" "framer-motion:Framer Motion" '"motion":Motion' "aos:AOS" \
            "animejs:Anime.js" "@react-spring:React Spring" "lottie:Lottie" \
            "locomotive-scroll:Locomotive"; do
  pat="${pair%%:*}"; name="${pair#*:}"
  [ "$(count "\"$pat[^\"]*\" *:")" != 0 ] && libs="$libs$name, "
done
libs="${libs%, }"
[ -n "$libs" ] && echo && echo "[i] библиотеки анимации в зависимостях: $libs"
if [ "$(printf '%s' "$libs" | tr ',' '\n' | grep -c .)" -gt 1 ]; then
  say стоп "две библиотеки анимации разом" \
    "оставить одну: React — motion, статика — AOS, закрепление экрана — GSAP" "$libs"
fi

say стоп "заголовок первого экрана появляется скриптом" \
  "убрать анимацию с h1: это LCP, метрика считается по появлению, а без JS там пусто" \
  "$(scan '<motion\.h1|<h1[^>]*(opacity-0|animate-[a-z]|data-aos|initial=)')"

# prefers-reduced-motion нужен только там, где движение вообще есть.
anim=$(count '@keyframes|transition:|transition-|animate-[a-z]|data-aos|<motion\.|useAnimate|gsap\.')
if [ "$anim" != 0 ] && [ "$(count 'prefers-reduced-motion|useReducedMotion')" = 0 ]; then
  say стоп "движение без prefers-reduced-motion" \
    "добавить медиа-запрос с animation-duration/transition-duration .01ms (образец в SKILL.md)" \
    "найдено мест с анимацией: $anim, выключателя нет"
fi

echo
echo "=== Внимание: так сайт кажется медленным ==="

say внимание "что-то крутится вечно в поле зрения" \
  "оставить только индикатор загрузки: телефон не спит, глаз цепляется" \
  "$(scan 'animate-(pulse|bounce|spin|ping)|iteration-count: *infinite|[0-9]s +[a-z-]+ +infinite|repeat: *Infinity')"

say внимание "движение дольше секунды" \
  "150–250 мс интерфейс, 300–600 мс появление; дольше — сайт кажется тормозящим" \
  "$(scan 'duration-(1000|1[5-9]00|[2-9][0-9]{3})|duration: *([1-9]|1\.[5-9])[,}) ]|(transition|animation):[^;]*[^0-9.]([2-9]|[1-9][0-9]+)s')"

say внимание "transition: all" \
  "перечислить свойства: под all рано или поздно попадает раскладка и кадры проседают" \
  "$(scan 'transition: *all|transition-all')"

say внимание "анимируется раскладка, а не transform" \
  "переделать на transform и opacity: остальное пересчитывает страницу на каждом кадре" \
  "$(scan 'transition:[^;]*\b(width|height|top|left|right|bottom|margin|padding)\b|@keyframes[^{]*\{[^}]*\b(width|height|margin):')"

say внимание "приезд издалека" \
  "8–24 px достаточно; 100 px читаются как «сайт ещё собирается»" \
  "$(scan 'translateY\(-?([5-9][0-9]|[1-9][0-9]{2,})px|y: *-?([5-9][0-9]|[1-9][0-9]{2,})[,}) ]')"

if [ "$(count 'ScrollTrigger|pin: *true|parallax')" != 0 ] && [ "$(count 'matchMedia')" = 0 ]; then
  say внимание "параллакс или закрепление экрана без мобильного отключения" \
    "обернуть в ScrollTrigger.matchMedia или (min-width: 768px): на телефоне это рвёт прокрутку" \
    "$(scan 'ScrollTrigger|pin: *true|parallax')"
fi

wc=$(count 'will-change')
[ "${wc:-0}" -gt 5 ] && say внимание "will-change расставлен подряд" \
  "оставить на паре элементов: каждый такой слой держится в памяти видеокарты" \
  "мест: $wc"

echo
if [ "$STOP" = 1 ]; then
  echo "Есть «стоп» — показывать и выкладывать нельзя."
else
  echo "«Стопов» нет. Дальше глазами: playwright на узком экране, прокрутка до конца, консоль."
fi
exit "$STOP"
