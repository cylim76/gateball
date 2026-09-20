#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
  echo "未找到 python3。请先安装：sudo apt install -y python3"
  exit 1
fi

missing_packages=()
python3 -c 'import tkinter' >/dev/null 2>&1 || missing_packages+=(python3-tk)
python3 -c 'import serial' >/dev/null 2>&1 || missing_packages+=(python3-serial)

if [ "${#missing_packages[@]}" -gt 0 ]; then
  echo "缺少运行依赖：${missing_packages[*]}"
  echo "正在安装……"
  sudo apt-get update || exit 1
  sudo apt-get install -y "${missing_packages[@]}" || exit 1
fi

if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
  echo "没有检测到 Linux 桌面显示环境。请进入 GB2 桌面后再运行此工具。"
  exit 1
fi

preferred_port=""
if [ -d /dev/serial/by-id ]; then
  preferred_port="$(find /dev/serial/by-id -maxdepth 1 -type l -print 2>/dev/null | sort | head -n 1)"
fi
if [ -z "$preferred_port" ] && [ -e /dev/ttyUSB0 ]; then
  preferred_port="/dev/ttyUSB0"
fi

if [ -n "$preferred_port" ]; then
  exec python3 esp32_usb_range_test.py --port "$preferred_port" "$@"
else
  exec python3 esp32_usb_range_test.py "$@"
fi
