#!/usr/bin/env bash
#
# Собрать «Выкладку» в готовое приложение. Выполняется НА МАКЕ ВЛАДЕЛЬЦА:
#
#   cd ~/site-scanner/macos/Vykladka && ./sobrat.sh
#
# Нужны инструменты командной строки Xcode (один раз: xcode-select --install).
# Полного Xcode не требуется, проекта .xcodeproj в репозитории нет намеренно:
# SwiftPM-пакет читается глазами и нормально ложится в git, а .xcodeproj — нет.

set -euo pipefail
cd "$(dirname "$0")"

IMYA_PROGRAMMY="Vykladka"
IMYA_APP="Выкладка.app"

echo "==> Собираю…"
swift build -c release

BINAR="$(swift build -c release --show-bin-path)/$IMYA_PROGRAMMY"
if [[ ! -x "$BINAR" ]]; then
    echo "Сборка не дала исполняемый файл: $BINAR" >&2
    exit 1
fi

echo "==> Складываю $IMYA_APP"
rm -rf "$IMYA_APP"
mkdir -p "$IMYA_APP/Contents/MacOS" "$IMYA_APP/Contents/Resources"
cp "$BINAR" "$IMYA_APP/Contents/MacOS/$IMYA_PROGRAMMY"
cp Resources/Info.plist "$IMYA_APP/Contents/Info.plist"

# Подпись «для себя». Без неё macOS ругается на неподписанную программу, а
# Связка ключей всё равно спросит разрешение при первом обращении после каждой
# пересборки — это нормально, жмите «Всегда разрешать».
echo "==> Подписываю для себя"
codesign --force --sign - --timestamp=none "$IMYA_APP" >/dev/null 2>&1 || \
    echo "    подписать не вышло — приложение всё равно запустится"

echo
echo "Готово: $(pwd)/$IMYA_APP"
echo "Перетащите его в /Applications или запустите так:"
echo "    open \"$(pwd)/$IMYA_APP\""
