#!/usr/bin/env bash
# Запускает веб-интерфейс site-scanner.
set -euo pipefail
cd "$(dirname "$0")"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8600}"
export HOST PORT

python -m webapp
