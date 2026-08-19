#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${1:-}" == "-decode" ]]; then
  GPIO_PIN="${2:-17}"
  echo "433MHz decode debug mode"
  echo "GPIO: BCM ${GPIO_PIN}"
  echo "Backend: lgpio"
  echo "Press a remote button. Send dump lines to Codex if no decoded code appears."
  exec python3 "$SCRIPT_DIR/rf_hex_test.py" \
    --gpio "$GPIO_PIN" \
    --backend lgpio \
    --dump-pulses 120 \
    --gap-us 20000 \
    --min-pulses 8
fi

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
