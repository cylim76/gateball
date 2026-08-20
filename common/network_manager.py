from __future__ import annotations

import platform
import shutil
import socket
import subprocess
import os


DEFAULT_HOTSPOT_SSID = "HongxingMenqiu1"
DEFAULT_HOTSPOT_PASSWORD = "1234567890"
HOTSPOT_CONNECTION = "gateball-ap"
HOTSPOT_IFNAME = "wlan0_ap"
HOTSPOT_ADDRESS = "192.168.1.1"
HOTSPOT_CIDR = f"{HOTSPOT_ADDRESS}/24"
HOTSPOT_APPLY_HELPER = "/usr/local/bin/gateball-network-apply"
SHORT_HOSTS = ("gateball", "menqiu")


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


def run_hotspot_apply_helper(ssid: str, password: str) -> dict | None:
    if platform.system().lower() != "linux" or not shutil.which("sudo") or not os.path.exists(HOTSPOT_APPLY_HELPER):
        return None
    try:
        result = subprocess.run(
            ["sudo", "-n", HOTSPOT_APPLY_HELPER, ssid, password],
            capture_output=True,
            check=False,
            text=True,
            timeout=50,
        )
    except Exception as exc:
        return {"ok": False, "supported": True, "message": str(exc)}
    if result.returncode != 0:
        return {
            "ok": False,
            "supported": True,
            "message": result.stderr.strip() or result.stdout.strip() or "热点 helper 执行失败",
        }
    return {"ok": True, "supported": True, "message": result.stdout.strip() or f"热点已更新：{ssid}"}


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
                if len(parts) >= 3 and parts[1] == "wifi" and parts[0] != HOTSPOT_CONNECTION:
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
        "hotspotSsid": state.get("hotspotSsid") or DEFAULT_HOTSPOT_SSID,
        "hotspotPassword": state.get("hotspotPassword") or DEFAULT_HOTSPOT_PASSWORD,
        "hotspotAddress": "http://gateball",
        "secondaryHotspotAddress": "http://menqiu",
        "fallbackAddress": f"http://{HOTSPOT_ADDRESS}:8000",
        "localAddresses": local_ipv4_addresses(),
        "activeWifi": active_wifi,
        "internetOk": internet_ok,
        "error": error,
    }


def configure_hotspot(ssid: str, password: str) -> dict:
    ssid = (ssid or DEFAULT_HOTSPOT_SSID).strip()[:32] or DEFAULT_HOTSPOT_SSID
    password = (password or DEFAULT_HOTSPOT_PASSWORD).strip()[:63] or DEFAULT_HOTSPOT_PASSWORD
    if len(password) < 8:
        return {"ok": False, "supported": True, "message": "热点密码至少 8 位"}
    if platform.system().lower() != "linux" or not command_available("nmcli"):
        return {"ok": True, "supported": False, "message": "已保存；当前系统不支持自动配置热点"}

    helper_result = run_hotspot_apply_helper(ssid, password)
    if helper_result is not None:
        return helper_result

    exists = run_nmcli(["connection", "show", HOTSPOT_CONNECTION], timeout=8)
    if exists.returncode != 0:
        create = run_nmcli(
            [
                "device",
                "wifi",
                "hotspot",
                "ifname",
                HOTSPOT_IFNAME,
                "con-name",
                HOTSPOT_CONNECTION,
                "ssid",
                ssid,
                "password",
                password,
            ],
            timeout=45,
        )
        if create.returncode != 0:
            return {
                "ok": False,
                "supported": True,
                "message": create.stderr.strip() or create.stdout.strip() or "热点创建失败",
            }

    modify = run_nmcli(
        [
            "connection",
            "modify",
            HOTSPOT_CONNECTION,
            "connection.autoconnect",
            "yes",
            "802-11-wireless.mode",
            "ap",
            "802-11-wireless.ssid",
            ssid,
            "ipv4.method",
            "shared",
            "ipv4.addresses",
            HOTSPOT_CIDR,
            "ipv6.method",
            "ignore",
            "wifi-sec.key-mgmt",
            "wpa-psk",
            "wifi-sec.psk",
            password,
        ],
        timeout=20,
    )
    if modify.returncode != 0:
        return {
            "ok": False,
            "supported": True,
            "message": modify.stderr.strip() or modify.stdout.strip() or "热点配置更新失败",
        }

    up = run_nmcli(["connection", "up", HOTSPOT_CONNECTION], timeout=45)
    if up.returncode != 0:
        return {
            "ok": False,
            "supported": True,
            "message": up.stderr.strip() or up.stdout.strip() or "热点已保存，启动热点失败，重启后可再确认",
        }
    return {"ok": True, "supported": True, "message": f"热点已更新：{ssid}"}


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
