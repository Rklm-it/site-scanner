#!/bin/bash
# Кладёт в репозиторий клиента объявление плагина со скилами студии.
# После этого любая сессия на этом репозитории — в терминале и в браузере —
# ставит скилы сама при запуске. Обновлять копии не надо: плагин тянется из
# site-scanner, там правка доезжает до всех клиентов разом.
#
#   ./tools/new-client.sh ~/work/rostov-steel-forge
set -euo pipefail

REPO="${1:-}"
[ -n "$REPO" ] || { echo "usage: $0 <путь к склонированному репозиторию клиента>" >&2; exit 2; }
[ -d "$REPO/.git" ] || { echo "не репозиторий: $REPO" >&2; exit 2; }

SETTINGS="$REPO/.claude/settings.json"

if [ -f "$SETTINGS" ]; then
  # Не затираем: у клиента могут быть свои разрешения и переменные.
  python3 - "$SETTINGS" <<'PY'
import json, sys
path = sys.argv[1]
with open(path, encoding='utf-8') as f:
    data = json.load(f)
data.setdefault('extraKnownMarketplaces', {})['rklm'] = {
    'source': {'source': 'github', 'repo': 'Rklm-it/site-scanner'}}
data.setdefault('enabledPlugins', {})['studio@rklm'] = True
with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
    f.write('\n')
print('дописано в существующий settings.json')
PY
else
  mkdir -p "$REPO/.claude"
  cat > "$SETTINGS" <<'J'
{
  "extraKnownMarketplaces": {
    "rklm": {
      "source": { "source": "github", "repo": "Rklm-it/site-scanner" }
    }
  },
  "enabledPlugins": { "studio@rklm": true }
}
J
  echo "создан $SETTINGS"
fi

git -C "$REPO" add .claude/settings.json
git -C "$REPO" commit -q -m "Скилы студии подключаются плагином из site-scanner

Чтобы сессия на этом репозитории знала наш цикл работы: разбор выгрузки,
промпты для Lovable по блокам, проверку следов конструктора и признаков
генерации перед показом клиенту." || echo "нечего коммитить — файл уже был такой"

cat <<'TXT'

Осталось запушить:
  git -C <репозиторий> push

Проверить: открыть сессию в этом репозитории и набрать /skills —
в списке должен появиться studio (и /lovable-site среди команд).

Если Lovable при следующей синхронизации выкинет .claude/ —
запускать Клода с двумя папками:
  claude --add-dir /root/site-scanner-main
TXT
