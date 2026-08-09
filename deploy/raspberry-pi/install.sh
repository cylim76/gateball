#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

GATEBALL_DIR="${GATEBALL_DIR:-$REPO_DIR}"
GATEBALL_USER="${GATEBALL_USER:-$(id -un)}"
INSTALL_KIOSK="${INSTALL_KIOSK:-1}"
SERVICE_NAME="${SERVICE_NAME:-gateball.service}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required."
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required. Install it with: sudo apt install curl"
  exit 1
fi

echo "Installing Gateball service"
echo "Project: $GATEBALL_DIR"
echo "User:    $GATEBALL_USER"

sudo install -d /etc/systemd/system
sed \
  -e "s#__GATEBALL_DIR__#$GATEBALL_DIR#g" \
  -e "s#__GATEBALL_USER__#$GATEBALL_USER#g" \
  "$SCRIPT_DIR/gateball.service.template" | sudo tee "/etc/systemd/system/$SERVICE_NAME" >/dev/null

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

if [ "$INSTALL_KIOSK" = "1" ]; then
  chmod +x "$SCRIPT_DIR/start-kiosk.sh"
  AUTOSTART_DIR="$HOME/.config/autostart"
  mkdir -p "$AUTOSTART_DIR"
  sed "s#__GATEBALL_DIR__#$GATEBALL_DIR#g" \
    "$SCRIPT_DIR/gateball-kiosk.desktop" > "$AUTOSTART_DIR/gateball-kiosk.desktop"
  chmod +x "$AUTOSTART_DIR/gateball-kiosk.desktop"
  echo "Kiosk autostart installed: $AUTOSTART_DIR/gateball-kiosk.desktop"
fi

echo
echo "Installed."
echo "Service status: sudo systemctl status $SERVICE_NAME"
echo "Service logs:   journalctl -u $SERVICE_NAME -f"
echo "Scoreboard:     http://127.0.0.1:8000/scoreboard"
echo "Remote:         http://127.0.0.1:8000/remote"
