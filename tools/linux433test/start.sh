#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "433MHz remote GPIO test"
echo "Use BCM GPIO number, not physical pin number."
echo "Example: BCM GPIO17 is physical pin 11."
echo
read -r -p "Input BCM GPIO number [17]: " GPIO_PIN
GPIO_PIN="${GPIO_PIN:-17}"
echo
echo "Backend options:"
echo "  lgpio   - recommended for this remote test; bypasses rpi-rf"
echo "  auto    - try rpi-rf first, then fallback"
echo "  rpi-rf  - use rpi-rf only"
echo "  rpi-gpio - use RPi.GPIO polling only"
read -r -p "Input backend [lgpio]: " BACKEND
BACKEND="${BACKEND:-lgpio}"

exec python3 "$SCRIPT_DIR/rf_hex_test.py" --gpio "$GPIO_PIN" --backend "$BACKEND"
