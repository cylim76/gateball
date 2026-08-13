#!/usr/bin/env bash
set -euo pipefail

GATEBALL_URL="${GATEBALL_URL:-http://127.0.0.1:8000/scoreboard?kiosk=1}"
WAIT_URL="${WAIT_URL:-http://127.0.0.1:8000/api/state}"
CHROMIUM_PROFILE_DIR="${CHROMIUM_PROFILE_DIR:-/tmp/gateball-chromium-profile}"

for _ in $(seq 1 90); do
  if curl -fsS "$WAIT_URL" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if command -v xset >/dev/null 2>&1; then
  xset s off || true
  xset -dpms || true
  xset s noblank || true
fi

pkill -f "chromium.*${GATEBALL_URL}" 2>/dev/null || true
rm -rf "$CHROMIUM_PROFILE_DIR" 2>/dev/null || true
mkdir -p "$CHROMIUM_PROFILE_DIR"

CHROMIUM_BIN=""
for candidate in chromium-browser chromium chromium-browser-stable; do
  if command -v "$candidate" >/dev/null 2>&1; then
    CHROMIUM_BIN="$candidate"
    break
  fi
done

if [ -z "$CHROMIUM_BIN" ]; then
  echo "Chromium is not installed. Try: sudo apt install chromium-browser"
  exit 1
fi

exec "$CHROMIUM_BIN" \
  --kiosk \
  --user-data-dir="$CHROMIUM_PROFILE_DIR" \
  --password-store=basic \
  --no-first-run \
  --no-default-browser-check \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-features=Translate,AutofillServerCommunication \
  --autoplay-policy=no-user-gesture-required \
  --check-for-update-interval=31536000 \
  "$GATEBALL_URL"
