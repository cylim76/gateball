#!/usr/bin/env bash
set -euo pipefail

UPLINK_IFNAME="${GATEBALL_UPLINK_IFNAME:-wlan0}"
HOTSPOT_IFNAME="${GATEBALL_HOTSPOT_IFNAME:-wlan0_ap}"
HOTSPOT_CONNECTION="${GATEBALL_HOTSPOT_CONNECTION:-gateball-ap}"
LOCK_FILE="${GATEBALL_NETWORK_SYNC_LOCK:-/run/gateball-network-sync.lock}"

log() {
  printf 'Gateball network sync: %s\n' "$*"
}

frequency_to_channel() {
  local frequency="${1//[^0-9]/}"
  if [ "$frequency" = "2484" ]; then
    printf '14\n'
  elif [ -n "$frequency" ] && [ "$frequency" -ge 2412 ] && [ "$frequency" -le 2472 ]; then
    printf '%s\n' "$(( (frequency - 2407) / 5 ))"
  fi
}

linked_frequency() {
  iw dev "$1" link 2>/dev/null | sed -n 's/^[[:space:]]*freq: \([0-9][0-9]*\).*/\1/p' | head -n1
}

configured_hotspot_channel() {
  nmcli -g 802-11-wireless.channel connection show "$HOTSPOT_CONNECTION" 2>/dev/null | head -n1
}

active_hotspot_channel() {
  local frequency=""
  frequency="$(iw dev "$HOTSPOT_IFNAME" info 2>/dev/null | sed -n 's/.*channel [0-9][0-9]* (\([0-9][0-9]*\) MHz).*/\1/p' | head -n1)"
  frequency_to_channel "$frequency"
}

main() {
  command -v nmcli >/dev/null 2>&1 || exit 0
  command -v iw >/dev/null 2>&1 || exit 0

  if command -v flock >/dev/null 2>&1; then
    mkdir -p "$(dirname "$LOCK_FILE")"
    exec 9>"$LOCK_FILE"
    flock -n 9 || exit 0
  fi

  if [ "${1:-}" = "--recover-uplink" ]; then
    log "uplink disconnected; pausing $HOTSPOT_CONNECTION before reconnecting $UPLINK_IFNAME"
    nmcli connection down "$HOTSPOT_CONNECTION" >/dev/null 2>&1 || true
    nmcli --wait 25 device connect "$UPLINK_IFNAME" >/dev/null 2>&1 || true
    for _ in 1 2 3 4 5; do
      [ -n "$(linked_frequency "$UPLINK_IFNAME")" ] && break
      sleep 1
    done
    if [ -z "$(linked_frequency "$UPLINK_IFNAME")" ]; then
      log "uplink is still unavailable; restoring the local hotspot"
      nmcli connection up "$HOTSPOT_CONNECTION" >/dev/null 2>&1 || true
      exit 0
    fi
  fi

  local uplink_connection=""
  local uplink_frequency=""
  local desired_channel=""
  local uplink_band=""
  local pinned_bssid=""
  local saved_channel=""
  local live_channel=""
  local hotspot_active=""

  uplink_connection="$(nmcli -g GENERAL.CONNECTION device show "$UPLINK_IFNAME" 2>/dev/null | head -n1 || true)"
  uplink_frequency="$(linked_frequency "$UPLINK_IFNAME")"
  desired_channel="$(frequency_to_channel "$uplink_frequency")"
  if [ -z "$uplink_connection" ] || [ "$uplink_connection" = "--" ] || [ -z "$desired_channel" ]; then
    exit 0
  fi

  # Keep the uplink on 2.4 GHz, but allow NetworkManager to choose any BSSID
  # advertising the saved SSID. This survives router and mesh-node replacement.
  uplink_band="$(nmcli -g 802-11-wireless.band connection show "$uplink_connection" 2>/dev/null | head -n1 || true)"
  pinned_bssid="$(nmcli -g 802-11-wireless.bssid connection show "$uplink_connection" 2>/dev/null | head -n1 || true)"
  if [ "$uplink_band" != "bg" ] || [ -n "$pinned_bssid" ]; then
    nmcli connection modify "$uplink_connection" \
      802-11-wireless.band bg \
      802-11-wireless.bssid ""
  fi

  nmcli connection show "$HOTSPOT_CONNECTION" >/dev/null 2>&1 || exit 0
  saved_channel="$(configured_hotspot_channel)"
  live_channel="$(active_hotspot_channel)"
  if nmcli -t -f NAME connection show --active 2>/dev/null | grep -Fxq "$HOTSPOT_CONNECTION"; then
    hotspot_active=1
  fi

  if [ -n "$hotspot_active" ] \
    && [ "$saved_channel" = "$desired_channel" ] \
    && [ "$live_channel" = "$desired_channel" ]; then
    exit 0
  fi

  log "aligning $HOTSPOT_CONNECTION with $UPLINK_IFNAME on channel $desired_channel"
  if [ -n "$hotspot_active" ]; then
    nmcli connection down "$HOTSPOT_CONNECTION" >/dev/null 2>&1 || true
  fi
  nmcli connection modify "$HOTSPOT_CONNECTION" \
    802-11-wireless.band bg \
    802-11-wireless.channel "$desired_channel"
  nmcli connection up "$HOTSPOT_CONNECTION"
}

main "$@"
