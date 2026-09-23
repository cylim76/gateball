#!/usr/bin/env bash
# Targeted kiosk power policy; safe to apply without reinstalling or reconnecting Wi-Fi.
set -euo pipefail

POWER_MARKER="# Managed by Gateball power policy."
NM_POWER_CONF="/etc/NetworkManager/conf.d/90-gateball-power.conf"
NM_POWER_DISPATCHER="/etc/NetworkManager/dispatcher.d/90-gateball-power"
SLEEP_POWER_CONF="/etc/systemd/sleep.conf.d/90-gateball-power.conf"
IDLE_POWER_CONF="/etc/systemd/logind.conf.d/90-gateball-power.conf"

write_power_file() {
  local path="$1" mode="$2"
  if [ ! -d "$(dirname "$path")" ]; then
    install -d -m 755 "$(dirname "$path")"
  fi
  if [ -e "$path" ] || [ -L "$path" ]; then
    if ! grep -Fxq "$POWER_MARKER" "$path"; then
      if [ -e "$path.gateball.bak" ] || [ -L "$path.gateball.bak" ]; then
        echo "Refusing to overwrite an unmanaged power file with an existing backup: $path" >&2
        return 1
      fi
      cp -a "$path" "$path.gateball.bak"
    fi
    rm -f "$path"
  fi
  cat > "$path"
  chmod "$mode" "$path"
}

remove_power_file() {
  local path="$1"
  if [ -e "$path" ] || [ -L "$path" ]; then
    if ! grep -Fxq "$POWER_MARKER" "$path"; then
      echo "Keeping unmanaged file: $path"
      return
    fi
    rm -f "$path"
  fi
  if [ -e "$path.gateball.bak" ] || [ -L "$path.gateball.bak" ]; then
    mv "$path.gateball.bak" "$path"
  fi
}

reload_power_defaults() {
  if command -v nmcli >/dev/null 2>&1 && nmcli general status >/dev/null 2>&1; then
    nmcli general reload conf || echo "Warning: Wi-Fi defaults will apply after NetworkManager next starts." >&2
  fi
  # Do not restart NetworkManager or logind: doing so can interrupt SSH/the display.
}

install_power_policy() {
  write_power_file "$NM_POWER_CONF" 644 <<EOF
$POWER_MARKER
[connection]
wifi.powersave=2
EOF
  write_power_file "$SLEEP_POWER_CONF" 644 <<EOF
$POWER_MARKER
[Sleep]
AllowSuspend=no
AllowHibernation=no
AllowHybridSleep=no
AllowSuspendThenHibernate=no
EOF
  write_power_file "$IDLE_POWER_CONF" 644 <<EOF
$POWER_MARKER
[Login]
IdleAction=ignore
EOF
  write_power_file "$NM_POWER_DISPATCHER" 755 <<'EOF'
#!/bin/sh
# Managed by Gateball power policy.
# Also cover saved profiles that explicitly enable power saving.
case "${2:-}" in up|reapply) ;; *) exit 0 ;; esac
command -v iw >/dev/null 2>&1 || exit 0
iw dev "$1" info >/dev/null 2>&1 || exit 0
iw dev "$1" set power_save off || echo "Gateball: cannot disable Wi-Fi power saving on $1" >&2
EOF
  reload_power_defaults
  if command -v iw >/dev/null 2>&1; then
    while IFS= read -r ifname; do
      [ -n "$ifname" ] || continue
      iw dev "$ifname" set power_save off || echo "Warning: cannot disable Wi-Fi power saving on $ifname" >&2
    done < <(iw dev | awk '$1 == "Interface" { print $2 }')
  else
    echo "Warning: iw is unavailable; Wi-Fi defaults apply on the next connection." >&2
  fi
  echo "Disabled Wi-Fi power saving and system suspend/hibernation."
  echo "IdleAction=ignore takes effect the next time logind starts (normally after reboot)."
  echo "CPU scaling, thermal protection, and normal shutdown remain available."
}

remove_power_policy() {
  local path
  for path in "$NM_POWER_DISPATCHER" "$NM_POWER_CONF" "$SLEEP_POWER_CONF" "$IDLE_POWER_CONF"; do
    remove_power_file "$path"
  done
  reload_power_defaults
  echo "Removed Gateball power policy; restored pre-existing files when backed up."
  echo "Wi-Fi settings take effect on reconnect; idle settings take effect after reboot."
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  if [ "$(id -u)" != "0" ]; then
    echo "Run with sudo: sudo bash $0 [install|remove]" >&2
    exit 1
  fi
  case "${1:-install}" in
    install) install_power_policy ;;
    remove) remove_power_policy ;;
    *) echo "Usage: $0 [install|remove]" >&2; exit 2 ;;
  esac
fi
