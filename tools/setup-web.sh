#!/bin/bash
# Ставит плагины студии в облачной сессии. Вписывается в поле «Setup script»
# окружения Claude Code — выполняется один раз при подготовке контейнера, до
# запуска Клода.
#
# Зачем отдельный скрипт, если есть setup-machine.sh: тот пишет объявление в
# settings.json, а объявление плагин НЕ СТАВИТ. Проверено на чистом окружении:
# `.claude/settings.json` с enabledPlugins есть, а `claude plugin list` пуст и
# инструментов mcp__* в сессии нет. Установка — это клон маркетплейса, и в
# облаке её никто не подтвердит, поэтому здесь она вызывается явно.
#
# Идемпотентен: повторный запуск обновляет маркетплейс и переустанавливает.
set -uo pipefail

MARKETPLACE="Rklm-it/site-scanner"

echo "== плагины студии =="
if claude plugin marketplace add "$MARKETPLACE" 2>/dev/null; then
  echo "маркетплейс добавлен"
else
  claude plugin marketplace update rklm >/dev/null 2>&1 && echo "маркетплейс обновлён" \
    || { echo "не удалось получить маркетплейс $MARKETPLACE" >&2; exit 1; }
fi

# studio ставим только там, где скилов нет в самом репозитории: в сканере они
# лежат в .claude/skills и грузятся напрямую, вторая копия из плагина только
# путает список.
PLUGINS=(playwright context7 stitch)
[ -d ".claude/skills" ] || PLUGINS+=(studio)

for p in "${PLUGINS[@]}"; do
  claude plugin install "$p@rklm" >/dev/null 2>&1 && echo "  + $p" || echo "  ! $p не встал" >&2
done

# Ключ Stitch приходит переменной окружения площадки, а не отсюда: в репозитории
# ему не место. Без него сервер поднимется, но каждый вызов вернёт отказ.
[ -n "${STITCH_API_KEY:-}" ] && echo "ключ Stitch: есть" || echo "ключ Stitch: НЕТ (добавь STITCH_API_KEY в переменные окружения)"
