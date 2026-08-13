from __future__ import annotations

import platform
import shutil
import socket
import subprocess


def command_available(name: str) -> bool:
    return shutil.which(name) is not None


def run_nmcli(args: list[str], timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["nmcli", *args],
        capture_output=True,
        check=False,
        text=True,
        timeout=timeout,
    )


def split_nmcli_terse(line: str) -> list[str]:
    parts: list[str] = []
    current = []
    escaped = False
    for char in line:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    parts.append("".join(current))
    return parts


def local_ipv4_addresses() -> list[str]:
    addresses: set[str] = set()
    try:
        for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = item[4][0]
            if not address.startswith("127."):
                addresses.add(address)
    except OSError:
        pass
    return sorted(addresses)


def network_status(state: dict) -> dict:
    supported = platform.system().lower() == "linux" and command_available("nmcli")
    active_wifi = ""
    internet_ok = False
    error = ""

    if supported:
        try:
            active = run_nmcli(["-t", "-f", "NAME,TYPE,DEVICE", "connection", "show", "--active"], timeout=8)
            for line in active.stdout.splitlines():
                parts = split_nmcli_terse(line)
                if len(parts) >= 3 and parts[1] == "wifi":
                    active_wifi = parts[0]
                    break
            internet = subprocess.run(
                ["ping", "-c", "1", "-W", "2", "223.5.5.5"],
                capture_output=True,
                check=False,
                text=True,
                timeout=5,
            )
            internet_ok = internet.returncode == 0
        except Exception as exc:
            error = str(exc)

    return {
        "ok": True,
        "supported": supported,
        "platform": platform.system(),
        "nmcli": command_available("nmcli"),
        "courtName": state.get("courtName", ""),
        "hotspotSsid": state.get("hotspotSsid", ""),
        "hotspotPassword": state.get("hotspotPassword", ""),
        "hotspotAddress": "http://menqiu.hongxing",
        "fallbackAddress": "http://192.168.50.1:8000",
        "localAddresses": local_ipv4_addresses(),
        "activeWifi": active_wifi,
        "internetOk": internet_ok,
        "error": error,
    }


def scan_wifi_networks() -> dict:
    if platform.system().lower() != "linux" or not command_available("nmcli"):
        return {"ok": False, "supported": False, "networks": [], "message": "当前系统不支持 WiFi 扫描"}

    result = run_nmcli(["-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list", "--rescan", "yes"], timeout=18)
    if result.returncode != 0:
        return {"ok": False, "supported": True, "networks": [], "message": result.stderr.strip() or "WiFi 扫描失败"}

    networks: dict[str, dict] = {}
    for line in result.stdout.splitlines():
        parts = split_nmcli_terse(line)
        if len(parts) < 2:
            continue
        ssid = parts[0].strip()
        if not ssid:
            continue
        try:
            signal = int(parts[1] or "0")
        except ValueError:
            signal = 0
        security = parts[2].strip() if len(parts) > 2 else ""
        current = networks.get(ssid)
        if current is None or signal > current["signal"]:
            networks[ssid] = {"ssid": ssid, "signal": signal, "security": security}

    return {
        "ok": True,
        "supported": True,
        "networks": sorted(networks.values(), key=lambda item: item["signal"], reverse=True),
    }


def connect_wifi(ssid: str, password: str) -> dict:
    if platform.system().lower() != "linux" or not command_available("nmcli"):
        return {"ok": False, "supported": False, "message": "当前系统不支持 WiFi 连接"}
    ssid = ssid.strip()
    if not ssid:
        return {"ok": False, "supported": True, "message": "请选择 WiFi"}

    args = ["dev", "wifi", "connect", ssid]
    if password:
        args.extend(["password", password])
    result = run_nmcli(args, timeout=35)
    if result.returncode != 0:
        return {
            "ok": False,
            "supported": True,
            "message": result.stderr.strip() or result.stdout.strip() or "WiFi 连接失败，热点会继续保留",
        }
    return {"ok": True, "supported": True, "message": "WiFi 连接成功", "ssid": ssid}
