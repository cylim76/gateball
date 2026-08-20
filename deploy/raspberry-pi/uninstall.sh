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
RESTART_DISPLAY_MANAGER="${RESTART_DISPLAY_MANAGER:-0}"
REMOVE_NETWORK_SUPPORT="${REMOVE_NETWORK_SUPPORT:-1}"
GATEBALL_HOTSPOT_CONNECTION="${GATEBALL_HOTSPOT_CONNECTION:-gateball-ap}"
NGINX_GATEBALL_SITE="/etc/nginx/sites-available/gateball"
NGINX_GATEBALL_SITE_ENABLED="/etc/nginx/sites-enabled/gateball"
NM_DNSMASQ_CONF="/etc/NetworkManager/dnsmasq.d/gateball.conf"
NM_DNSMASQ_SHARED_CONF="/etc/NetworkManager/dnsmasq-shared.d/gateball.conf"
NETWORK_APPLY_HELPER="/usr/local/bin/gateball-network-apply"
NETWORK_SUDOERS_FILE="/etc/sudoers.d/gateball-network"

enable_display_manager() {
  sudo systemctl set-default graphical.target
  if [ -e /etc/systemd/system/display-manager.service ]; then
    sudo systemctl enable display-manager.service >/dev/null 2>&1 || true
    if [ "$RESTART_DISPLAY_MANAGER" = "1" ]; then
      echo "Restarting display-manager.service because RESTART_DISPLAY_MANAGER=1"
      sudo systemctl restart display-manager.service >/dev/null 2>&1 || true
    else
      echo "Display manager enabled; reboot to apply without closing this terminal."
    fi
    return
  fi

  for service in lightdm.service wayfire.service gdm3.service sddm.service; do
    if systemctl list-unit-files "$service" 2>/dev/null | grep -q "^$service"; then
      sudo systemctl enable "$service" >/dev/null 2>&1 || true
      if [ "$RESTART_DISPLAY_MANAGER" = "1" ]; then
        echo "Restarting $service because RESTART_DISPLAY_MANAGER=1"
        sudo systemctl restart "$service" >/dev/null 2>&1 || true
      else
        echo "$service enabled; reboot to apply without closing this terminal."
      fi
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

remove_network_support() {
  if [ "$REMOVE_NETWORK_SUPPORT" != "1" ]; then
    echo "Gateball network cleanup skipped: REMOVE_NETWORK_SUPPORT=$REMOVE_NETWORK_SUPPORT"
    return
  fi

  if command -v nmcli >/dev/null 2>&1; then
    sudo nmcli connection delete "$GATEBALL_HOTSPOT_CONNECTION" >/dev/null 2>&1 || true
  fi
  sudo rm -f "$NGINX_GATEBALL_SITE_ENABLED" "$NGINX_GATEBALL_SITE"
  sudo rm -f "$NM_DNSMASQ_CONF" "$NM_DNSMASQ_SHARED_CONF"
  sudo rm -f "$NETWORK_APPLY_HELPER" "$NETWORK_SUDOERS_FILE"
  if command -v nginx >/dev/null 2>&1; then
    sudo nginx -t >/dev/null 2>&1 && sudo systemctl reload nginx >/dev/null 2>&1 || true
  fi
  sudo systemctl restart NetworkManager >/dev/null 2>&1 || true
  echo "Removed Gateball hotspot, nginx site, and local DNS name configuration."
}

sudo systemctl disable --now "$SERVICE_NAME" 2>/dev/null || true
sudo systemctl disable --now "$DIRECT_X_SERVICE_NAME" 2>/dev/null || true
sudo rm -f "/etc/systemd/system/$SERVICE_NAME"
sudo rm -f "$DIRECT_X_SERVICE_FILE"
sudo systemctl daemon-reload

rm -f "$AUTOSTART_FILE"
sudo rm -f "$KIOSK_SESSION_RUNNER" "$KIOSK_XSESSION_FILE" "$LIGHTDM_KIOSK_CONF"
remove_network_support
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
