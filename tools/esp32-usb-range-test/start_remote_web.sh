#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
  echo "未找到 python3。请先安装：sudo apt install -y python3"
  exit 1
fi

if ! python3 -c 'import serial' >/dev/null 2>&1; then
  echo "缺少 python3-serial，正在安装……"
  sudo apt-get update || exit 1
  sudo apt-get install -y python3-serial || exit 1
fi

device="${ESP32_SERIAL_DEVICE:-}"
if [ -z "$device" ] && [ -d /dev/serial/by-id ]; then
  device="$(find /dev/serial/by-id -maxdepth 1 -type l -print 2>/dev/null | sort | head -n 1)"
fi
if [ -z "$device" ]; then
  device="/dev/ttyUSB0"
fi

gateball_was_active=0
cleanup() {
  if [ "$gateball_was_active" = 1 ]; then
    echo
    echo "正在恢复 Gateball 服务……"
    sudo systemctl start gateball.service || true
  fi
}
trap cleanup EXIT INT TERM

if systemctl is-active --quiet gateball.service; then
  echo "Gateball 正在占用 USB 串口，测试期间将暂停该服务。"
  sudo systemctl stop gateball.service || exit 1
  gateball_was_active=1
fi

host_ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo
echo "ESP32 USB 远程测试正在运行"
echo "串口：$device"
echo "Windows 浏览器打开：http://${host_ip:-192.168.1.221}:8765"
echo "测试结束请在这里按 Ctrl+C；Gateball 服务会自动恢复。"
echo

python3 esp32_usb_range_test_web.py --host 0.0.0.0 --port 8765 --device "$device"
