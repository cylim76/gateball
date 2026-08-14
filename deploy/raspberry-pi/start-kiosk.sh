#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATEBALL_URL="${GATEBALL_URL:-http://127.0.0.1:8000/scoreboard?kiosk=1}"
WAIT_URL="${WAIT_URL:-http://127.0.0.1:8000/api/state}"
CHROMIUM_PROFILE_DIR="${CHROMIUM_PROFILE_DIR:-/tmp/gateball-chromium-profile}"
SPLASH_URL="${SPLASH_URL:-file://${SCRIPT_DIR}/splash/splash.html}"
WAIT_SECONDS="${WAIT_SECONDS:-180}"
MIN_SPLASH_SECONDS="${MIN_SPLASH_SECONDS:-5}"
LOG_FILE="${LOG_FILE:-/tmp/gateball-kiosk.log}"

exec >>"$LOG_FILE" 2>&1
echo
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Gateball kiosk starting"
echo "Script: $SCRIPT_DIR"
echo "Splash: $SPLASH_URL"
echo "Scoreboard: $GATEBALL_URL"

if command -v xset >/dev/null 2>&1; then
  xset s off || true
  xset -dpms || true
  xset s noblank || true
fi

if command -v xsetroot >/dev/null 2>&1; then
  xsetroot -solid black || true
fi

pkill -f "chromium.*${GATEBALL_URL}" 2>/dev/null || true
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
echo "Chromium: $CHROMIUM_BIN"

pkill -f "chromium.*${SPLASH_URL}" 2>/dev/null || true
pkill -f "chromium.*${GATEBALL_URL}" 2>/dev/null || true
rm -rf "$CHROMIUM_PROFILE_DIR" 2>/dev/null || true
mkdir -p "$CHROMIUM_PROFILE_DIR"

CHROMIUM_ARGS=(
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
  --check-for-update-interval=31536000
)

"$CHROMIUM_BIN" "${CHROMIUM_ARGS[@]}" "$SPLASH_URL" &
SPLASH_PID="$!"
SPLASH_STARTED_AT="$(date +%s)"
echo "Splash browser started: pid=$SPLASH_PID"

for _ in $(seq 1 "$WAIT_SECONDS"); do
  if curl -fsS "$WAIT_URL" >/dev/null 2>&1; then
    echo "Backend is ready: $WAIT_URL"
    break
  fi
  sleep 1
done

SPLASH_ELAPSED="$(($(date +%s) - SPLASH_STARTED_AT))"
if [ "$SPLASH_ELAPSED" -lt "$MIN_SPLASH_SECONDS" ]; then
  sleep "$((MIN_SPLASH_SECONDS - SPLASH_ELAPSED))"
fi

kill "$SPLASH_PID" 2>/dev/null || true
pkill -f "chromium.*${SPLASH_URL}" 2>/dev/null || true
sleep 0.4

echo "Opening scoreboard"
exec "$CHROMIUM_BIN" "${CHROMIUM_ARGS[@]}" "$GATEBALL_URL"
