#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REBOOT=0
CAPTURE=0

usage() {
    cat <<'EOF'
Usage: ./install.sh [--capture] [--reboot]

  --capture  Capture EDID from a currently connected working TV input.
  --reboot   Reboot automatically after installation.

Without --capture, the verified bundled LG TV EDID is installed.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --capture) CAPTURE=1 ;;
        --reboot) REBOOT=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

COMPATIBLE_FILE="${PI_HDMI_COMPATIBLE_FILE:-/proc/device-tree/compatible}"
MODEL_FILE="${PI_HDMI_MODEL_FILE:-/proc/device-tree/model}"
BOARD_MODEL="hardware check overridden"

# This package changes Raspberry Pi KMS/vc4 boot parameters.  Unsupported
# boards must leave before sudo is requested or any file is modified.
if [[ "${PI_HDMI_ALLOW_UNSUPPORTED:-0}" != "1" ]]; then
    if [[ ! -r "$COMPATIBLE_FILE" ]] || \
        ! tr '\0' '\n' < "$COMPATIBLE_FILE" | grep -q '^raspberrypi,'; then
        echo "pi-hdmi-active: unsupported non-Raspberry-Pi board; skipped safely."
        exit 0
    fi

    BOARD_MODEL="$(tr -d '\0' < "$MODEL_FILE" 2>/dev/null || true)"
    case "$BOARD_MODEL" in
        Raspberry\ Pi\ 4*|Raspberry\ Pi\ 5*|Raspberry\ Pi\ 400*) ;;
        *)
            echo "pi-hdmi-active: unsupported Raspberry Pi model '$BOARD_MODEL'; skipped safely."
            exit 0
            ;;
    esac
fi

if [[ $EUID -eq 0 ]]; then
    echo "Run this script as the desktop user, not with sudo." >&2
    echo "The script will request sudo only for system files." >&2
    exit 1
fi

for command in sudo systemctl pactl awk sed grep stat; do
    command -v "$command" >/dev/null || { echo "Missing command: $command" >&2; exit 1; }
done

sudo -n true 2>/dev/null || sudo -v

USER_NAME="$(id -un)"
USER_HOME="$HOME"
USER_ID="$(id -u)"
STATE_DIR="/var/lib/pi-hdmi-active"
EDID_TARGET="/lib/firmware/pi-hdmi-active-edid.bin"
CMDLINE_FILE="/boot/firmware/cmdline.txt"
INITRAMFS_HOOK="/etc/initramfs-tools/hooks/pi-hdmi-active-edid"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
TEMP_EDID=""

cleanup() {
    [[ -n "$TEMP_EDID" && -f "$TEMP_EDID" ]] && rm -f -- "$TEMP_EDID"
    return 0
}
trap cleanup EXIT

if [[ ! -f "$CMDLINE_FILE" ]]; then
    echo "Unsupported layout: $CMDLINE_FILE was not found." >&2
    exit 1
fi

EDID_SOURCE="$SCRIPT_DIR/assets/lg-tv-edid.bin"
if [[ $CAPTURE -eq 1 ]]; then
    TEMP_EDID="$(mktemp)"
    EDID_SOURCE=""
    for candidate in /sys/class/drm/card*-HDMI-A-1/edid /sys/class/drm/card*-HDMI-A-2/edid; do
        if [[ -r "$candidate" && "$(stat -c %s "$candidate")" -ge 128 ]]; then
            cp -- "$candidate" "$TEMP_EDID"
            EDID_SOURCE="$TEMP_EDID"
            echo "Captured EDID from $candidate"
            break
        fi
    done
    if [[ -z "$EDID_SOURCE" ]]; then
        echo "No valid connected-display EDID was found." >&2
        echo "Connect the TV to an input that returns EDID, then retry --capture." >&2
        exit 1
    fi
fi

EDID_SIZE="$(stat -c %s "$EDID_SOURCE")"
if (( EDID_SIZE < 128 || EDID_SIZE % 128 != 0 )); then
    echo "Invalid EDID size: $EDID_SIZE bytes" >&2
    exit 1
fi

sudo install -d -m 755 "$STATE_DIR/backups"
sudo cp -- "$CMDLINE_FILE" "$STATE_DIR/backups/cmdline.txt.$TIMESTAMP"
sudo install -m 644 "$EDID_SOURCE" "$EDID_TARGET"
sudo install -m 755 "$SCRIPT_DIR/assets/initramfs-hook" "$INITRAMFS_HOOK"

CURRENT_CMDLINE="$(cat "$CMDLINE_FILE")"
NEW_TOKENS=()
for token in $CURRENT_CMDLINE; do
    case "$token" in
        drm.edid_firmware=HDMI-A-1:lg-tv-hdmi3.bin,HDMI-A-2:lg-tv-hdmi3.bin) ;;
        drm.edid_firmware=HDMI-A-1:pi-hdmi-active-edid.bin,HDMI-A-2:pi-hdmi-active-edid.bin) ;;
        vc4.force_hotplug=2) ;;
        video=HDMI-A-2:1920x1080@60D) ;;
        *) NEW_TOKENS+=("$token") ;;
    esac
done
NEW_TOKENS+=(
    "drm.edid_firmware=HDMI-A-1:pi-hdmi-active-edid.bin,HDMI-A-2:pi-hdmi-active-edid.bin"
    "vc4.force_hotplug=2"
    "video=HDMI-A-2:1920x1080@60D"
)
printf '%s\n' "${NEW_TOKENS[*]}" | sudo tee "$CMDLINE_FILE" >/dev/null

sudo /usr/sbin/update-initramfs -u -k all

install -d -m 755 "$USER_HOME/.local/bin" "$USER_HOME/.config/systemd/user"
install -m 755 "$SCRIPT_DIR/pi-hdmi-active" "$USER_HOME/.local/bin/pi-hdmi-active"
install -m 644 "$SCRIPT_DIR/systemd/pi-hdmi-active.service" \
    "$USER_HOME/.config/systemd/user/pi-hdmi-active.service"

sudo loginctl enable-linger "$USER_NAME"
systemctl --user daemon-reload
systemctl --user enable --now pi-hdmi-active.service

echo
echo "pi-hdmi-active installed for $USER_NAME (uid $USER_ID)."
echo "Board: $BOARD_MODEL"
echo "EDID: $EDID_TARGET ($EDID_SIZE bytes)"
echo "Policy: prefer physical HDMI0; otherwise use forced HDMI1."
echo "Status: $USER_HOME/.local/bin/pi-hdmi-active status"
echo "Logs: journalctl --user -u pi-hdmi-active.service"

if [[ $REBOOT -eq 1 ]]; then
    echo "Rebooting now..."
    sudo systemctl reboot
else
    echo "Reboot is required to activate the EDID and HDMI1 boot parameters."
fi
