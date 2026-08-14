#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

GATEBALL_DIR="${GATEBALL_DIR:-$REPO_DIR}"
GATEBALL_USER="${GATEBALL_USER:-$(id -un)}"
INSTALL_KIOSK="${INSTALL_KIOSK:-1}"
CONFIGURE_QUIET_BOOT="${CONFIGURE_QUIET_BOOT:-1}"
SERVICE_NAME="${SERVICE_NAME:-gateball.service}"

backup_once() {
  local path="$1"
  if [ -f "$path" ] && [ ! -f "${path}.gateball.bak" ]; then
    sudo cp "$path" "${path}.gateball.bak"
  fi
}

ensure_cmdline_arg() {
  local path="$1"
  local arg="$2"
  if [ ! -f "$path" ]; then
    return
  fi
  if ! tr ' ' '\n' < "$path" | grep -Fxq "$arg"; then
    backup_once "$path"
    sudo sed -i "s/$/ $arg/" "$path"
  fi
}

ensure_config_line() {
  local path="$1"
  local line="$2"
  if [ ! -f "$path" ]; then
    return
  fi
  if ! grep -Fxq "$line" "$path"; then
    backup_once "$path"
    printf '%s\n' "$line" | sudo tee -a "$path" >/dev/null
  fi
}

configure_quiet_boot() {
  local cmdline_file=""
  local config_file=""

  for candidate in /boot/firmware/cmdline.txt /boot/cmdline.txt; do
    if [ -f "$candidate" ]; then
      cmdline_file="$candidate"
      break
    fi
  done

  for candidate in /boot/firmware/config.txt /boot/config.txt; do
    if [ -f "$candidate" ]; then
      config_file="$candidate"
      break
    fi
  done

  if [ -n "$cmdline_file" ]; then
    for arg in quiet loglevel=3 vt.global_cursor_default=0 logo.nologo consoleblank=0 plymouth.enable=0; do
      ensure_cmdline_arg "$cmdline_file" "$arg"
    done
    echo "Quiet boot arguments configured: $cmdline_file"
  else
    echo "Boot cmdline file not found; skipped quiet boot arguments."
  fi

  if [ -n "$config_file" ]; then
    ensure_config_line "$config_file" "disable_splash=1"
    echo "Raspberry Pi rainbow splash disabled: $config_file"
  else
    echo "Boot config file not found; skipped Raspberry Pi splash setting."
  fi

  for service in plymouth-start.service plymouth-quit.service plymouth-quit-wait.service; do
    if systemctl list-unit-files "$service" 2>/dev/null | grep -q "^$service"; then
      sudo systemctl mask "$service" >/dev/null 2>&1 || true
      echo "Plymouth service masked: $service"
    fi
  done
}

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

if [ "$CONFIGURE_QUIET_BOOT" = "1" ]; then
  configure_quiet_boot
fi

echo
echo "Installed."
echo "Service status: sudo systemctl status $SERVICE_NAME"
echo "Service logs:   journalctl -u $SERVICE_NAME -f"
echo "Scoreboard:     http://127.0.0.1:8000/scoreboard"
echo "Kiosk:          http://127.0.0.1:8000/scoreboard?kiosk=1"
echo "Remote:         http://127.0.0.1:8000/remote"
echo
echo "Reboot the Raspberry Pi to apply boot splash and quiet boot changes."
