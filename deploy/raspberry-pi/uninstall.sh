#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-gateball.service}"
AUTOSTART_FILE="$HOME/.config/autostart/gateball-kiosk.desktop"

sudo systemctl disable --now "$SERVICE_NAME" 2>/dev/null || true
sudo rm -f "/etc/systemd/system/$SERVICE_NAME"
sudo systemctl daemon-reload

rm -f "$AUTOSTART_FILE"

echo "Removed Gateball service and kiosk autostart."
