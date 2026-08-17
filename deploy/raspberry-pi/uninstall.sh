#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-gateball.service}"
DIRECT_X_SERVICE_NAME="${DIRECT_X_SERVICE_NAME:-gateball-x-kiosk.service}"
DEFAULT_GATEBALL_USER="$(id -un)"
if [ "$DEFAULT_GATEBALL_USER" = "root" ] && [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
  DEFAULT_GATEBALL_USER="$SUDO_USER"
fi
GATEBALL_USER="${GATEBALL_USER:-$DEFAULT_GATEBALL_USER}"
GATEBALL_HOME="$(getent passwd "$GATEBALL_USER" | cut -d: -f6)"
if [ -z "$GATEBALL_HOME" ]; then
  GATEBALL_HOME="$HOME"
fi
AUTOSTART_FILE="$GATEBALL_HOME/.config/autostart/gateball-kiosk.desktop"
KIOSK_SESSION_RUNNER="/usr/local/bin/gateball-kiosk-session"
KIOSK_XSESSION_FILE="/usr/share/xsessions/gateball-kiosk.desktop"
LIGHTDM_KIOSK_CONF="/etc/lightdm/lightdm.conf.d/99-gateball-kiosk.conf"
DIRECT_X_SERVICE_FILE="/etc/systemd/system/$DIRECT_X_SERVICE_NAME"
XWRAPPER_CONFIG="/etc/X11/Xwrapper.config"
REMOVE_KIOSK_PACKAGES="${REMOVE_KIOSK_PACKAGES:-0}"

enable_display_manager() {
  sudo systemctl set-default graphical.target
  if [ -e /etc/systemd/system/display-manager.service ]; then
    sudo systemctl enable display-manager.service >/dev/null 2>&1 || true
    sudo systemctl restart display-manager.service >/dev/null 2>&1 || true
    return
  fi

  for service in lightdm.service wayfire.service gdm3.service sddm.service; do
    if systemctl list-unit-files "$service" 2>/dev/null | grep -q "^$service"; then
      sudo systemctl enable "$service" >/dev/null 2>&1 || true
      sudo systemctl restart "$service" >/dev/null 2>&1 || true
      return
    fi
  done
}

restore_desktop_shell() {
  if [ -n "${DISPLAY:-}" ] && command -v pcmanfm >/dev/null 2>&1; then
    pcmanfm --desktop >/dev/null 2>&1 || true
  fi
  if [ -n "${DISPLAY:-}" ] && command -v lxpanel >/dev/null 2>&1 && ! pgrep -x lxpanel >/dev/null 2>&1; then
    lxpanel >/tmp/gateball-lxpanel-restore.log 2>&1 &
  fi
  if [ -n "${DISPLAY:-}" ] && command -v wf-panel-pi >/dev/null 2>&1 && ! pgrep -x wf-panel-pi >/dev/null 2>&1; then
    wf-panel-pi >/tmp/gateball-wf-panel-restore.log 2>&1 &
  fi
}

restore_boot_file() {
  local path="$1"
  if [ -f "${path}.gateball.bak" ]; then
    sudo mv "${path}.gateball.bak" "$path"
    echo "Restored boot file: $path"
  fi
}

sudo systemctl disable --now "$SERVICE_NAME" 2>/dev/null || true
sudo systemctl disable --now "$DIRECT_X_SERVICE_NAME" 2>/dev/null || true
sudo rm -f "/etc/systemd/system/$SERVICE_NAME"
sudo rm -f "$DIRECT_X_SERVICE_FILE"
sudo systemctl daemon-reload

rm -f "$AUTOSTART_FILE"
sudo rm -f "$KIOSK_SESSION_RUNNER" "$KIOSK_XSESSION_FILE" "$LIGHTDM_KIOSK_CONF"
enable_display_manager
restore_desktop_shell

restore_boot_file /boot/firmware/cmdline.txt
restore_boot_file /boot/cmdline.txt
restore_boot_file /boot/firmware/config.txt
restore_boot_file /boot/config.txt
restore_boot_file "$XWRAPPER_CONFIG"

for service in plymouth-start.service plymouth-quit.service plymouth-quit-wait.service; do
  sudo systemctl unmask "$service" >/dev/null 2>&1 || true
done

if [ "$REMOVE_KIOSK_PACKAGES" = "1" ]; then
  sudo apt-get remove -y xserver-xorg xinit openbox
fi

echo "Removed Gateball service, kiosk autostart, and restored Gateball boot splash changes when backups existed."
