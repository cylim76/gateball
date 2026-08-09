#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Cleaning old Gateball web server processes..."

if command -v lsof >/dev/null 2>&1; then
  old_pids="$(lsof -ti tcp:8000 -sTCP:LISTEN || true)"
  if [ -n "$old_pids" ]; then
    echo "$old_pids" | xargs -r kill
    sleep 0.3
    echo "$old_pids" | xargs -r kill -9 2>/dev/null || true
  fi
elif command -v fuser >/dev/null 2>&1; then
  fuser -k 8000/tcp 2>/dev/null || true
fi

pkill -f "web/server.py" 2>/dev/null || true
pkill -f "web/server.py" 2>/dev/null || true

echo "Starting Gateball web server..."
echo "Scoreboard: http://127.0.0.1:8000/scoreboard"
echo "Remote:     http://127.0.0.1:8000/remote"
echo "Settings:   http://127.0.0.1:8000/set"
echo
echo "Press Ctrl+C to stop."
echo

python3 web/server.py

