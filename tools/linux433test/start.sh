#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${1:-}" == "" || "${1:-}" == "-decode" || "${1:-}" == "-decoded" ]]; then
  GPIO_PIN="${2:-17}"
  echo "433MHz decode debug mode"
  echo "GPIO: BCM ${GPIO_PIN}"
  echo "Backend: lgpio"
  echo "Only decoded codes will be shown. Use -dump if raw pulses are needed."
  exec python3 "$SCRIPT_DIR/rf_hex_test.py" \
    --gpio "$GPIO_PIN" \
    --backend lgpio \
    --gap-us 20000 \
    --min-pulses 8
fi

if [[ "${1:-}" == "-dump" ]]; then
  GPIO_PIN="${2:-17}"
  echo "433MHz raw pulse dump mode"
  echo "GPIO: BCM ${GPIO_PIN}"
  echo "Backend: lgpio"
  echo "Press a remote button. Send dump lines to Codex if no decoded code appears."
  exec python3 "$SCRIPT_DIR/rf_hex_test.py" \
    --gpio "$GPIO_PIN" \
    --backend lgpio \
    --dump-pulses 120 \
    --gap-us 20000 \
    --min-pulses 8 \
    --show-raw
fi

if [[ "${1:-}" != "-interactive" ]]; then
  echo "Unknown option: ${1:-}"
  echo "Usage:"
  echo "  bash start.sh              # decode mode, GPIO17"
  echo "  bash start.sh -decode 25   # decode mode, selected GPIO"
  echo "  bash start.sh -dump 17     # raw pulse dump mode"
  echo "  bash start.sh -interactive # choose GPIO/backend manually"
  exit 2
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
