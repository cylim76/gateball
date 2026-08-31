#!/usr/bin/env bash
set -euo pipefail

REBOOT=0
if [[ "${1:-}" == "--reboot" ]]; then
    REBOOT=1
elif [[ $# -gt 0 ]]; then
    echo "Usage: ./uninstall.sh [--reboot]" >&2
    exit 2
fi

if [[ $EUID -eq 0 ]]; then
    echo "Run this script as the desktop user, not with sudo." >&2
    exit 1
fi

sudo -n true 2>/dev/null || sudo -v

CMDLINE_FILE="/boot/firmware/cmdline.txt"
STATE_DIR="/var/lib/pi-hdmi-active"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

systemctl --user disable --now pi-hdmi-active.service 2>/dev/null || true
rm -f -- "$HOME/.config/systemd/user/pi-hdmi-active.service"
rm -f -- "$HOME/.local/bin/pi-hdmi-active"
systemctl --user daemon-reload

if [[ -f "$CMDLINE_FILE" ]]; then
    sudo install -d -m 755 "$STATE_DIR/backups"
    sudo cp -- "$CMDLINE_FILE" "$STATE_DIR/backups/cmdline-before-uninstall.$TIMESTAMP"
    CURRENT_CMDLINE="$(cat "$CMDLINE_FILE")"
    KEPT_TOKENS=()
    for token in $CURRENT_CMDLINE; do
        case "$token" in
            drm.edid_firmware=HDMI-A-1:pi-hdmi-active-edid.bin,HDMI-A-2:pi-hdmi-active-edid.bin) ;;
            vc4.force_hotplug=2) ;;
            video=HDMI-A-2:1920x1080@60D) ;;
            *) KEPT_TOKENS+=("$token") ;;
        esac
    done
    printf '%s\n' "${KEPT_TOKENS[*]}" | sudo tee "$CMDLINE_FILE" >/dev/null
fi

sudo rm -f -- /etc/initramfs-tools/hooks/pi-hdmi-active-edid
sudo rm -f -- /lib/firmware/pi-hdmi-active-edid.bin
sudo /usr/sbin/update-initramfs -u -k all

echo "pi-hdmi-active has been uninstalled. Backups remain in $STATE_DIR/backups."
if [[ $REBOOT -eq 1 ]]; then
    sudo systemctl reboot
else
    echo "Reboot is required to remove the boot-time HDMI settings from the running system."
fi
