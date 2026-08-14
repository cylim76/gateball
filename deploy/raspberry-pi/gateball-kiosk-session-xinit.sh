#!/usr/bin/env bash
set -euo pipefail

export DISPLAY="${DISPLAY:-:0}"
export LOG_FILE="${LOG_FILE:-/tmp/gateball-kiosk.log}"

if command -v xsetroot >/dev/null 2>&1; then
  xsetroot -solid black || true
fi

if command -v xset >/dev/null 2>&1; then
  xset s off || true
  xset -dpms || true
  xset s noblank || true
fi

if command -v openbox >/dev/null 2>&1; then
  openbox >/tmp/gateball-openbox.log 2>&1 &
else
  echo "openbox is not installed; Chromium will run without a window manager" >>"$LOG_FILE"
fi

exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/start-kiosk.sh"
