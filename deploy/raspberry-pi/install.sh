#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

GATEBALL_DIR="${GATEBALL_DIR:-$REPO_DIR}"
DEFAULT_GATEBALL_USER="$(id -un)"
if [ "$DEFAULT_GATEBALL_USER" = "root" ] && [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
  DEFAULT_GATEBALL_USER="$SUDO_USER"
fi
GATEBALL_USER="${GATEBALL_USER:-$DEFAULT_GATEBALL_USER}"
GATEBALL_HOME="$(getent passwd "$GATEBALL_USER" | cut -d: -f6)"
if [ -z "$GATEBALL_HOME" ]; then
  echo "Cannot determine home directory for user: $GATEBALL_USER"
  exit 1
fi
INSTALL_KIOSK="${INSTALL_KIOSK:-1}"
INSTALL_DESKTOP_AUTOSTART="${INSTALL_DESKTOP_AUTOSTART:-1}"
INSTALL_KIOSK_SESSION="${INSTALL_KIOSK_SESSION:-0}"
INSTALL_DIRECT_X_KIOSK="${INSTALL_DIRECT_X_KIOSK:-0}"
CONFIGURE_QUIET_BOOT="${CONFIGURE_QUIET_BOOT:-1}"
RESTART_DISPLAY_MANAGER="${RESTART_DISPLAY_MANAGER:-0}"
INSTALL_RF_SUPPORT="${INSTALL_RF_SUPPORT:-1}"
INSTALL_AUDIO_SUPPORT="${INSTALL_AUDIO_SUPPORT:-1}"
INSTALL_NETWORK_SUPPORT="${INSTALL_NETWORK_SUPPORT:-1}"
GATEBALL_HOTSPOT_SSID="${GATEBALL_HOTSPOT_SSID:-HongxingMenqiu1}"
GATEBALL_HOTSPOT_PASSWORD="${GATEBALL_HOTSPOT_PASSWORD:-1234567890}"
GATEBALL_HOTSPOT_CONNECTION="${GATEBALL_HOTSPOT_CONNECTION:-gateball-ap}"
GATEBALL_HOTSPOT_IFNAME="${GATEBALL_HOTSPOT_IFNAME:-wlan0_ap}"
GATEBALL_HOTSPOT_ADDRESS="${GATEBALL_HOTSPOT_ADDRESS:-192.168.1.1}"
SERVICE_NAME="${SERVICE_NAME:-gateball.service}"
DIRECT_X_SERVICE_NAME="${DIRECT_X_SERVICE_NAME:-gateball-x-kiosk.service}"
AUTOSTART_FILE="$GATEBALL_HOME/.config/autostart/gateball-kiosk.desktop"
KIOSK_SESSION_RUNNER="/usr/local/bin/gateball-kiosk-session"
KIOSK_XSESSION_FILE="/usr/share/xsessions/gateball-kiosk.desktop"
LIGHTDM_KIOSK_CONF="/etc/lightdm/lightdm.conf.d/99-gateball-kiosk.conf"
DIRECT_X_SERVICE_FILE="/etc/systemd/system/$DIRECT_X_SERVICE_NAME"
XWRAPPER_CONFIG="/etc/X11/Xwrapper.config"
DIRECT_X_PACKAGES=(xserver-xorg xinit openbox)
NGINX_GATEBALL_SITE="/etc/nginx/sites-available/gateball"
NGINX_GATEBALL_SITE_ENABLED="/etc/nginx/sites-enabled/gateball"
NM_DNSMASQ_CONF="/etc/NetworkManager/dnsmasq.d/gateball.conf"
NM_DNSMASQ_SHARED_CONF="/etc/NetworkManager/dnsmasq-shared.d/gateball.conf"
NETWORK_APPLY_HELPER="/usr/local/bin/gateball-network-apply"
NETWORK_SUDOERS_FILE="/etc/sudoers.d/gateball-network"
AP_INTERFACE_SERVICE_NAME="gateball-wlan-ap.service"
AP_INTERFACE_SERVICE_FILE="/etc/systemd/system/$AP_INTERFACE_SERVICE_NAME"

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

install_desktop_autostart() {
  chmod +x "$SCRIPT_DIR/start-kiosk.sh"
  local autostart_dir="$GATEBALL_HOME/.config/autostart"
  install -d -m 755 "$autostart_dir"
  sed "s#__GATEBALL_DIR__#$GATEBALL_DIR#g" \
    "$SCRIPT_DIR/gateball-kiosk.desktop" > "$AUTOSTART_FILE"
  chmod +x "$AUTOSTART_FILE"
  sudo chown -R "$GATEBALL_USER:$GATEBALL_USER" "$autostart_dir"
  echo "Kiosk desktop autostart installed: $AUTOSTART_FILE"
}

install_kiosk_session() {
  chmod +x "$SCRIPT_DIR/start-kiosk.sh"
  sudo install -d /usr/local/bin /usr/share/xsessions /etc/lightdm/lightdm.conf.d
  sed "s#__GATEBALL_DIR__#$GATEBALL_DIR#g" \
    "$SCRIPT_DIR/gateball-kiosk-session.sh.template" | sudo tee "$KIOSK_SESSION_RUNNER" >/dev/null
  sudo chmod +x "$KIOSK_SESSION_RUNNER"
  sudo install -m 644 "$SCRIPT_DIR/gateball-kiosk-xsession.desktop" "$KIOSK_XSESSION_FILE"
  sed "s#__GATEBALL_USER__#$GATEBALL_USER#g" \
    "$SCRIPT_DIR/gateball-lightdm.conf.template" | sudo tee "$LIGHTDM_KIOSK_CONF" >/dev/null
  rm -f "$AUTOSTART_FILE"
  echo "Dedicated kiosk session installed: $KIOSK_XSESSION_FILE"
  echo "LightDM kiosk autologin installed: $LIGHTDM_KIOSK_CONF"
}

remove_kiosk_session_config() {
  sudo rm -f "$KIOSK_SESSION_RUNNER" "$KIOSK_XSESSION_FILE" "$LIGHTDM_KIOSK_CONF"
}

install_direct_x_kiosk() {
  chmod +x "$SCRIPT_DIR/start-kiosk.sh" "$SCRIPT_DIR/gateball-kiosk-session-xinit.sh"
  echo "Installing direct X kiosk packages: ${DIRECT_X_PACKAGES[*]}"
  sudo apt-get update
  sudo apt-get install -y "${DIRECT_X_PACKAGES[@]}"
  rm -f "$AUTOSTART_FILE"
  remove_kiosk_session_config
  sudo install -d /etc/X11
  if [ -f "$XWRAPPER_CONFIG" ]; then
    backup_once "$XWRAPPER_CONFIG"
  fi
  {
    echo "allowed_users=anybody"
    echo "needs_root_rights=yes"
  } | sudo tee "$XWRAPPER_CONFIG" >/dev/null
  sudo systemctl disable --now lightdm.service display-manager.service >/dev/null 2>&1 || true
  sudo systemctl set-default multi-user.target
  sed \
    -e "s#__GATEBALL_DIR__#$GATEBALL_DIR#g" \
    -e "s#__GATEBALL_USER__#$GATEBALL_USER#g" \
    "$SCRIPT_DIR/gateball-x-kiosk.service.template" | sudo tee "$DIRECT_X_SERVICE_FILE" >/dev/null
  sudo systemctl daemon-reload
  sudo systemctl enable "$DIRECT_X_SERVICE_NAME"
  sudo systemctl restart "$DIRECT_X_SERVICE_NAME"
  echo "Direct X kiosk service installed: $DIRECT_X_SERVICE_FILE"
}

remove_direct_x_kiosk() {
  sudo systemctl disable --now "$DIRECT_X_SERVICE_NAME" >/dev/null 2>&1 || true
  sudo rm -f "$DIRECT_X_SERVICE_FILE"
  sudo systemctl daemon-reload
}

python_has_module() {
  local module_name="$1"
  python3 - "$module_name" <<'PY' >/dev/null 2>&1
import importlib.util
import sys
sys.exit(0 if importlib.util.find_spec(sys.argv[1]) else 1)
PY
}

pip_supports_break_system_packages() {
  python3 -m pip help install 2>/dev/null | grep -q -- "--break-system-packages"
}

install_rf_support() {
  if [ "$INSTALL_RF_SUPPORT" != "1" ]; then
    echo "RF GPIO support install skipped: INSTALL_RF_SUPPORT=$INSTALL_RF_SUPPORT"
    return
  fi

  echo "Installing RF GPIO decoder dependencies: python3-pip python3-rpi.gpio python3-lgpio rpi-rf"
  if ! sudo apt-get update || ! sudo apt-get install -y python3-pip python3-rpi.gpio python3-lgpio; then
    echo "Warning: failed to install RF GPIO apt dependencies. GPIO remote learning may not work yet."
    echo "Try manually: sudo apt install -y python3-pip python3-rpi.gpio python3-lgpio"
    return
  fi

  if python_has_module rpi_rf; then
    echo "RF GPIO decoder already installed: rpi-rf"
    return
  fi

  local pip_args=(install rpi-rf)
  if pip_supports_break_system_packages; then
    pip_args+=(--break-system-packages)
  fi

  if ! sudo python3 -m pip "${pip_args[@]}"; then
    echo "Warning: failed to install rpi-rf. GPIO remote learning will not work until rpi-rf is installed."
    echo "Try manually: sudo python3 -m pip install rpi-rf --break-system-packages"
    return
  fi

  if python_has_module rpi_rf; then
    echo "RF GPIO decoder installed: rpi-rf"
  else
    echo "Warning: rpi-rf installation finished, but python3 still cannot import rpi_rf."
  fi
}

install_audio_support() {
  if [ "$INSTALL_AUDIO_SUPPORT" != "1" ]; then
    echo "Audio output helper install skipped: INSTALL_AUDIO_SUPPORT=$INSTALL_AUDIO_SUPPORT"
    return
  fi
  if command -v pactl >/dev/null 2>&1; then
    echo "Audio output helper already available: pactl"
    return
  fi
  echo "Installing audio output helper: pulseaudio-utils"
  if ! sudo apt-get update || ! sudo apt-get install -y pulseaudio-utils; then
    echo "Warning: failed to install pulseaudio-utils. Manual audio output switching may need system sound settings."
  fi
}

wait_for_network_manager() {
  echo "Waiting for NetworkManager to become ready..."
  if command -v nm-online >/dev/null 2>&1; then
    sudo nm-online -q --timeout=15 || echo "Warning: nm-online timed out; continuing with nmcli readiness checks."
  fi
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    if nmcli general status >/dev/null 2>&1; then
      sleep 2
      return 0
    fi
    sleep 1
  done
  echo "Warning: NetworkManager did not report ready within 15 seconds."
  return 1
}

wait_for_hotspot_interface() {
  local ifname="$1"
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if ip link show "$ifname" >/dev/null 2>&1; then
      for _ in 1 2 3 4 5; do
        if nmcli -t -f DEVICE device status 2>/dev/null | grep -Fxq "$ifname"; then
          return 0
        fi
        sleep 1
      done
      echo "Warning: $ifname exists, but NetworkManager has not listed it yet."
      return 0
    fi
    sleep 1
  done
  echo "Hotspot interface not found: $ifname" >&2
  return 1
}

ensure_hotspot_profile() {
  local ifname="$1"
  local connection="$2"
  local ssid="$3"
  local password="$4"
  local address="$5"
  local create_output=""
  local up_output=""

  wait_for_hotspot_interface "$ifname" || return 1
  while IFS=: read -r active_name active_device; do
    if [ "$active_device" = "$ifname" ] && [ "$active_name" != "$connection" ]; then
      echo "Releasing active connection on $ifname: $active_name"
      sudo nmcli connection down "$active_name" || true
    fi
  done < <(nmcli -t -f NAME,DEVICE connection show --active 2>/dev/null || true)

  if ! sudo nmcli connection show "$connection" >/dev/null 2>&1; then
    for attempt in 1 2 3; do
      echo "Creating hotspot profile $connection on $ifname (attempt $attempt/3)..."
      if create_output="$(sudo nmcli device wifi hotspot ifname "$ifname" con-name "$connection" ssid "$ssid" password "$password" 2>&1)"; then
        echo "$create_output"
        break
      fi
      echo "Hotspot creation attempt $attempt failed:" >&2
      echo "$create_output" >&2
      sleep 2
    done
  fi

  if ! sudo nmcli connection show "$connection" >/dev/null 2>&1; then
    echo "Hotspot profile was not created: $connection" >&2
    nmcli device status >&2 || true
    return 1
  fi

  sudo nmcli connection modify "$connection" \
    connection.autoconnect yes \
    connection.interface-name "$ifname" \
    802-11-wireless.mode ap \
    802-11-wireless.ssid "$ssid" \
    ipv4.method shared \
    ipv4.addresses "$address/24" \
    ipv4.dns "$address" \
    ipv4.ignore-auto-dns yes \
    ipv6.method ignore \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "$password"

  for attempt in 1 2 3; do
    echo "Starting hotspot profile $connection (attempt $attempt/3)..."
    if up_output="$(sudo nmcli connection up "$connection" 2>&1)"; then
      echo "$up_output"
      break
    fi
    echo "Hotspot start attempt $attempt failed:" >&2
    echo "$up_output" >&2
    sleep 2
  done

  if ! nmcli -t -f NAME connection show --active 2>/dev/null | grep -Fxq "$connection"; then
    echo "Hotspot profile is not active after start attempt: $connection" >&2
    nmcli connection show "$connection" >&2 || true
    nmcli connection show --active >&2 || true
    nmcli device status >&2 || true
    return 1
  fi

  if command -v iw >/dev/null 2>&1; then
    if ! iw dev 2>/dev/null | awk -v iface="$ifname" '
      $1 == "Interface" { current = $2 }
      current == iface && $1 == "type" && $2 == "AP" { found = 1 }
      END { exit(found ? 0 : 1) }
    '; then
      echo "Warning: $ifname is active in NetworkManager, but iw does not currently report type AP."
      iw dev || true
    fi
  fi
}

print_hotspot_status() {
  local connection="$1"
  local ifname="$2"
  local ssid="$3"
  local address="$4"
  local profile_status="FAIL"
  local interface_status="FAIL"
  local state_status="FAIL"

  if sudo nmcli connection show "$connection" >/dev/null 2>&1; then
    profile_status="OK"
  fi
  if ip link show "$ifname" >/dev/null 2>&1; then
    interface_status="OK"
  fi
  if nmcli -t -f NAME connection show --active 2>/dev/null | grep -Fxq "$connection"; then
    state_status="OK"
  fi

  echo
  printf '%-34s %s\n' "Hotspot profile: $connection" "$profile_status"
  printf '%-34s %s\n' "Hotspot interface: $ifname" "$interface_status"
  printf '%-34s %s\n' "Hotspot state: active" "$state_status"
  printf 'SSID: %s\n' "$ssid"
  printf 'IP: %s\n' "$address"
}

install_network_support() {
  if [ "$INSTALL_NETWORK_SUPPORT" != "1" ]; then
    echo "Gateball network support skipped: INSTALL_NETWORK_SUPPORT=$INSTALL_NETWORK_SUPPORT"
    return
  fi

  if [ "${#GATEBALL_HOTSPOT_PASSWORD}" -lt 8 ] || [ "${#GATEBALL_HOTSPOT_PASSWORD}" -gt 63 ]; then
    echo "Warning: hotspot password must be 8-63 characters. Network support skipped."
    return
  fi

  echo "Installing Gateball network support: NetworkManager hotspot, nginx, local DNS names"
  if ! sudo apt-get update || ! sudo apt-get install -y network-manager nginx dnsmasq-base; then
    echo "Warning: failed to install network packages. Short names and hotspot may not work yet."
    return
  fi

  local base_wifi_ifname=""
  if nmcli -t -f DEVICE,TYPE device status 2>/dev/null | grep -Fxq "wlan0:wifi"; then
    base_wifi_ifname="wlan0"
  else
    base_wifi_ifname="$(nmcli -t -f DEVICE,TYPE device status 2>/dev/null | awk -F: '$2=="wifi"{print $1; exit}')"
  fi
  if [ -z "$base_wifi_ifname" ] && ip link show wlan0 >/dev/null 2>&1; then
    base_wifi_ifname="wlan0"
  fi
  if [ -z "$base_wifi_ifname" ]; then
    echo "Warning: no WiFi interface found. Network support installed, but hotspot was not configured."
    return
  fi

  if [ "$GATEBALL_HOTSPOT_IFNAME" != "$base_wifi_ifname" ]; then
    sudo apt-get install -y iw >/dev/null 2>&1 || true
    sudo tee "$AP_INTERFACE_SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=Create Gateball WiFi AP interface
Before=NetworkManager.service
After=sys-subsystem-net-devices-$base_wifi_ifname.device
Wants=sys-subsystem-net-devices-$base_wifi_ifname.device

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/sh -c 'ip link show "$GATEBALL_HOTSPOT_IFNAME" >/dev/null 2>&1 || iw dev "$base_wifi_ifname" interface add "$GATEBALL_HOTSPOT_IFNAME" type __ap'
ExecStop=/bin/sh -c 'ip link show "$GATEBALL_HOTSPOT_IFNAME" >/dev/null 2>&1 && iw dev "$GATEBALL_HOTSPOT_IFNAME" del || true'

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable "$AP_INTERFACE_SERVICE_NAME" >/dev/null 2>&1 || true
    sudo systemctl start "$AP_INTERFACE_SERVICE_NAME" >/dev/null 2>&1 || true
    if ! ip link show "$GATEBALL_HOTSPOT_IFNAME" >/dev/null 2>&1; then
      echo "Warning: could not create $GATEBALL_HOTSPOT_IFNAME; falling back to $base_wifi_ifname"
      GATEBALL_HOTSPOT_IFNAME="$base_wifi_ifname"
    fi
  fi

  sudo tee "$NETWORK_APPLY_HELPER" >/dev/null <<EOF
#!/usr/bin/env bash
set -euo pipefail
SSID="\${1:-$GATEBALL_HOTSPOT_SSID}"
PASSWORD="\${2:-$GATEBALL_HOTSPOT_PASSWORD}"
HOTSPOT_IFNAME="$GATEBALL_HOTSPOT_IFNAME"
HOTSPOT_CONNECTION="$GATEBALL_HOTSPOT_CONNECTION"
HOTSPOT_ADDRESS="$GATEBALL_HOTSPOT_ADDRESS"
if [ -z "\$SSID" ] || [ "\${#SSID}" -gt 32 ]; then
  echo "Invalid hotspot SSID" >&2
  exit 2
fi
if [ "\${#PASSWORD}" -lt 8 ] || [ "\${#PASSWORD}" -gt 63 ]; then
  echo "Invalid hotspot password" >&2
  exit 2
fi

wait_for_hotspot_interface() {
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if ip link show "\$HOTSPOT_IFNAME" >/dev/null 2>&1; then
      for _ in 1 2 3 4 5; do
        if nmcli -t -f DEVICE device status 2>/dev/null | grep -Fxq "\$HOTSPOT_IFNAME"; then
          return 0
        fi
        sleep 1
      done
      echo "Warning: \$HOTSPOT_IFNAME exists, but NetworkManager has not listed it yet."
      return 0
    fi
    sleep 1
  done
  echo "Hotspot interface not found: \$HOTSPOT_IFNAME" >&2
  return 1
}

wait_for_hotspot_interface

while IFS=: read -r active_name active_device; do
  if [ "\$active_device" = "\$HOTSPOT_IFNAME" ] && [ "\$active_name" != "\$HOTSPOT_CONNECTION" ]; then
    echo "Releasing active connection on \$HOTSPOT_IFNAME: \$active_name"
    nmcli connection down "\$active_name" || true
  fi
done < <(nmcli -t -f NAME,DEVICE connection show --active 2>/dev/null || true)

if ! nmcli connection show "\$HOTSPOT_CONNECTION" >/dev/null 2>&1; then
  for attempt in 1 2 3; do
    echo "Creating hotspot profile \$HOTSPOT_CONNECTION on \$HOTSPOT_IFNAME (attempt \$attempt/3)..."
    if output="\$(nmcli device wifi hotspot ifname "\$HOTSPOT_IFNAME" con-name "\$HOTSPOT_CONNECTION" ssid "\$SSID" password "\$PASSWORD" 2>&1)"; then
      echo "\$output"
      break
    fi
    echo "Hotspot creation attempt \$attempt failed:" >&2
    echo "\$output" >&2
    sleep 2
  done
fi

if ! nmcli connection show "\$HOTSPOT_CONNECTION" >/dev/null 2>&1; then
  echo "Hotspot profile was not created: \$HOTSPOT_CONNECTION" >&2
  nmcli device status >&2 || true
  exit 1
fi

nmcli connection modify "\$HOTSPOT_CONNECTION" \\
  connection.autoconnect yes \\
  connection.interface-name "\$HOTSPOT_IFNAME" \\
  802-11-wireless.mode ap \\
  802-11-wireless.ssid "\$SSID" \\
  ipv4.method shared \\
  ipv4.addresses "\$HOTSPOT_ADDRESS/24" \\
  ipv4.dns "\$HOTSPOT_ADDRESS" \\
  ipv4.ignore-auto-dns yes \\
  ipv6.method ignore \\
  wifi-sec.key-mgmt wpa-psk \\
  wifi-sec.psk "\$PASSWORD"

for attempt in 1 2 3; do
  echo "Starting hotspot profile \$HOTSPOT_CONNECTION (attempt \$attempt/3)..."
  if output="\$(nmcli connection up "\$HOTSPOT_CONNECTION" 2>&1)"; then
    echo "\$output"
    break
  fi
  echo "Hotspot start attempt \$attempt failed:" >&2
  echo "\$output" >&2
  sleep 2
done

if ! nmcli -t -f NAME connection show --active 2>/dev/null | grep -Fxq "\$HOTSPOT_CONNECTION"; then
  echo "Hotspot profile is not active: \$HOTSPOT_CONNECTION" >&2
  nmcli connection show "\$HOTSPOT_CONNECTION" >&2 || true
  nmcli connection show --active >&2 || true
  nmcli device status >&2 || true
  exit 1
fi
echo "Hotspot updated: \$SSID"
EOF
  sudo chmod 755 "$NETWORK_APPLY_HELPER"
  echo "$GATEBALL_USER ALL=(root) NOPASSWD: $NETWORK_APPLY_HELPER" | sudo tee "$NETWORK_SUDOERS_FILE" >/dev/null
  sudo chmod 440 "$NETWORK_SUDOERS_FILE"
  if ! sudo visudo -cf "$NETWORK_SUDOERS_FILE" >/dev/null 2>&1; then
    sudo rm -f "$NETWORK_SUDOERS_FILE"
    echo "Warning: sudoers check failed. Network settings may need manual sudo."
  fi

  sudo install -d /etc/NetworkManager/dnsmasq.d /etc/NetworkManager/dnsmasq-shared.d
  {
    echo "address=/gateball/$GATEBALL_HOTSPOT_ADDRESS"
    echo "address=/menqiu/$GATEBALL_HOTSPOT_ADDRESS"
  } | sudo tee "$NM_DNSMASQ_CONF" >/dev/null
  sudo cp "$NM_DNSMASQ_CONF" "$NM_DNSMASQ_SHARED_CONF"

  sudo install -d /etc/nginx/sites-available /etc/nginx/sites-enabled
  sudo tee "$NGINX_GATEBALL_SITE" >/dev/null <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name gateball menqiu $GATEBALL_HOTSPOT_ADDRESS _;

    location = / {
        return 302 /remote;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
  sudo ln -sf "$NGINX_GATEBALL_SITE" "$NGINX_GATEBALL_SITE_ENABLED"
  sudo rm -f /etc/nginx/sites-enabled/default
  if sudo nginx -t >/dev/null 2>&1; then
    sudo systemctl enable nginx >/dev/null 2>&1 || true
    sudo systemctl restart nginx >/dev/null 2>&1 || true
  else
    echo "Warning: nginx configuration test failed. Check: sudo nginx -t"
  fi

  if command -v nmcli >/dev/null 2>&1; then
    sudo systemctl restart NetworkManager
    wait_for_network_manager
    if [ "$GATEBALL_HOTSPOT_IFNAME" != "$base_wifi_ifname" ]; then
      sudo systemctl start "$AP_INTERFACE_SERVICE_NAME"
    fi
    ensure_hotspot_profile \
      "$GATEBALL_HOTSPOT_IFNAME" \
      "$GATEBALL_HOTSPOT_CONNECTION" \
      "$GATEBALL_HOTSPOT_SSID" \
      "$GATEBALL_HOTSPOT_PASSWORD" \
      "$GATEBALL_HOTSPOT_ADDRESS"
    print_hotspot_status \
      "$GATEBALL_HOTSPOT_CONNECTION" \
      "$GATEBALL_HOTSPOT_IFNAME" \
      "$GATEBALL_HOTSPOT_SSID" \
      "$GATEBALL_HOTSPOT_ADDRESS"
  else
    echo "Warning: nmcli not found. Hotspot was not configured."
    return 1
  fi

  echo "Gateball network entries:"
  echo "  Hotspot: $GATEBALL_HOTSPOT_SSID / $GATEBALL_HOTSPOT_PASSWORD"
  echo "  Interface: $GATEBALL_HOTSPOT_IFNAME"
  echo "  Remote:  http://gateball or http://menqiu"
  echo "  Backup:  http://$GATEBALL_HOTSPOT_ADDRESS:8000/remote"
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
echo "Home:    $GATEBALL_HOME"

install_rf_support
install_audio_support
install_network_support

sudo install -d /etc/systemd/system
sed \
  -e "s#__GATEBALL_DIR__#$GATEBALL_DIR#g" \
  -e "s#__GATEBALL_USER__#$GATEBALL_USER#g" \
  "$SCRIPT_DIR/gateball.service.template" | sudo tee "/etc/systemd/system/$SERVICE_NAME" >/dev/null

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

if [ "$INSTALL_KIOSK" = "1" ]; then
  if [ "$INSTALL_DESKTOP_AUTOSTART" = "1" ]; then
    remove_direct_x_kiosk
    remove_kiosk_session_config
    install_desktop_autostart
    enable_display_manager
  elif [ "$INSTALL_DIRECT_X_KIOSK" = "1" ]; then
    install_direct_x_kiosk
  elif [ "$INSTALL_KIOSK_SESSION" = "1" ]; then
    remove_direct_x_kiosk
    install_kiosk_session
  else
    remove_direct_x_kiosk
    remove_kiosk_session_config
    install_desktop_autostart
    enable_display_manager
  fi
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
