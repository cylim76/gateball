#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-gateball.service}"
AUTOSTART_FILE="$HOME/.config/autostart/gateball-kiosk.desktop"
KIOSK_SESSION_RUNNER="/usr/local/bin/gateball-kiosk-session"
KIOSK_XSESSION_FILE="/usr/share/xsessions/gateball-kiosk.desktop"
LIGHTDM_KIOSK_CONF="/etc/lightdm/lightdm.conf.d/99-gateball-kiosk.conf"

restore_boot_file() {
  local path="$1"
  if [ -f "${path}.gateball.bak" ]; then
    sudo mv "${path}.gateball.bak" "$path"
    echo "Restored boot file: $path"
  fi
}

sudo systemctl disable --now "$SERVICE_NAME" 2>/dev/null || true
sudo rm -f "/etc/systemd/system/$SERVICE_NAME"
sudo systemctl daemon-reload

rm -f "$AUTOSTART_FILE"
sudo rm -f "$KIOSK_SESSION_RUNNER" "$KIOSK_XSESSION_FILE" "$LIGHTDM_KIOSK_CONF"

restore_boot_file /boot/firmware/cmdline.txt
restore_boot_file /boot/cmdline.txt
restore_boot_file /boot/firmware/config.txt
restore_boot_file /boot/config.txt

for service in plymouth-start.service plymouth-quit.service plymouth-quit-wait.service; do
  sudo systemctl unmask "$service" >/dev/null 2>&1 || true
done

echo "Removed Gateball service, kiosk autostart, and restored Gateball boot splash changes when backups existed."
