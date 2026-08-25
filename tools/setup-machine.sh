#!/bin/bash
# Подключает скилы студии на всей машине разом: пишет объявление плагина в
# ~/.claude/settings.json. После этого любой репозиторий на этой машине —
# сканер, проект клиента, что угодно — открывается со скилами, и класть файл
# в каждый репозиторий не нужно.
#
# Выполнить один раз на каждой машине: на маке владельца и на сервере.
#   ./tools/setup-machine.sh
set -euo pipefail

SETTINGS="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json"
mkdir -p "$(dirname "$SETTINGS")"

python3 - "$SETTINGS" <<'PY'
import json, os, sys

path = sys.argv[1]
# Дописываем, а не перезаписываем: в пользовательских настройках уже могут
# лежать разрешения, модель и переменные, и снести их — вернуть вопросы на
# каждую команду.
data = {}
if os.path.exists(path):
    with open(path, encoding='utf-8') as f:
        text = f.read().strip()
    if text:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            sys.exit(f'{path} не разбирается как JSON ({exc}). Почини руками и повтори.')

data.setdefault('extraKnownMarketplaces', {})['rklm'] = {
    'source': {'source': 'github', 'repo': 'Rklm-it/site-scanner'}}
data.setdefault('enabledPlugins', {})['studio@rklm'] = True

with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
    f.write('\n')
print(f'записано: {path}')
PY

cat <<'TXT'

Проверить: открыть Клода в любой папке и набрать /skills — в списке должен
появиться studio, а среди команд /lovable-site.

Репозиторий сканера приватный, поэтому машине нужен доступ к нему по git.
На сервере он уже настроен (им пользуется sync.sh); на маке при первом запуске
git спросит логин и токен.

Веб-сессии эту настройку не видят: она на машине, а там каждый раз новый
контейнер. Для них — либо тот же кусок в поле «Setup script» окружения:

  mkdir -p ~/.claude && cat > ~/.claude/settings.json <<'JSON'
  {
    "extraKnownMarketplaces": {
      "rklm": { "source": { "source": "github", "repo": "Rklm-it/site-scanner" } }
    },
    "enabledPlugins": { "studio@rklm": true }
  }
  JSON

  — но сессия на репозитории клиента может не достать приватный сканер, у неё
  доступ только к присоединённым репозиториям. Надёжный путь для веба —
  ./tools/new-client.sh, он кладёт объявление в сам репозиторий клиента.
TXT
