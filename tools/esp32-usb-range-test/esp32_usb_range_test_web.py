#!/usr/bin/env python3
"""LAN web UI for testing the Gateball ESP32 433 MHz USB bridge."""

from __future__ import annotations

import argparse
import csv
import json
import threading
import time
from collections import Counter, deque
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import serial
from serial.tools import list_ports


BAUD = 115200
MAX_ROWS = 1000


def parse_signal(line: str) -> dict[str, str] | None:
    text = line.strip()
    if text.startswith("RFJSON:"):
        text = text.removeprefix("RFJSON:").strip()
    if not text.startswith("{"):
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not any(data.get(key) for key in ("raw", "address", "button")):
        return None
    return {
        "raw": str(data.get("raw") or data.get("code") or ""),
        "address": str(data.get("address") or ""),
        "button": str(data.get("button") or ""),
        "bits": str(data.get("bits") or ""),
        "pulseUs": str(data.get("pulseUs") or ""),
        "protocol": str(data.get("protocol") or ""),
    }


def choose_device(requested: str) -> str:
    if requested:
        return requested
    by_id = sorted(Path("/dev/serial/by-id").glob("*")) if Path("/dev/serial/by-id").is_dir() else []
    if by_id:
        return str(by_id[0])
    ports = list(list_ports.comports())
    if not ports:
        return "/dev/ttyUSB0"
    markers = ("cp210", "silicon labs", "usb to uart", "ch340", "ch341", "ftdi")
    ports.sort(
        key=lambda port: (
            -sum(marker in f"{port.device} {port.description} {port.hwid}".lower() for marker in markers),
            port.device,
        )
    )
    return ports[0].device


class Monitor:
    def __init__(self, device: str, baud: int) -> None:
        self.device = device
        self.baud = baud
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.serial_port: serial.Serial | None = None
        self.status = "正在连接"
        self.error = ""
        self.started_monotonic = time.monotonic()
        self.last_signal_monotonic: float | None = None
        self.longest_silence = 0.0
        self.total = 0
        self.recent: deque[float] = deque()
        self.signals: deque[dict[str, Any]] = deque(maxlen=MAX_ROWS)
        self.raw_lines: deque[dict[str, str]] = deque(maxlen=MAX_ROWS)
        self.button_counts: Counter[str] = Counter()
        self.log_path: Path | None = None
        self.log_file = None
        self.csv_writer: csv.writer | None = None
        self.thread = threading.Thread(target=self._reader_loop, daemon=True)

    def start(self) -> None:
        self._open_log()
        self.thread.start()

    def _open_log(self) -> None:
        log_dir = Path(__file__).resolve().parent / "logs"
        log_dir.mkdir(exist_ok=True)
        self.log_path = log_dir / f"range-test-web-{datetime.now():%Y%m%d-%H%M%S}.csv"
        self.log_file = self.log_path.open("w", newline="", encoding="utf-8-sig")
        self.csv_writer = csv.writer(self.log_file)
        self.csv_writer.writerow(
            ["time", "elapsed_seconds", "device", "raw", "address", "button", "bits", "pulse_us", "protocol"]
        )
        self.log_file.flush()

    def _reader_loop(self) -> None:
        try:
            self.serial_port = serial.Serial(self.device, self.baud, timeout=0.25)
            with self.lock:
                self.status = "监听中"
                self.error = ""
            while not self.stop_event.is_set():
                raw = self.serial_port.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                if line:
                    self._record_line(line)
        except (serial.SerialException, OSError) as exc:
            with self.lock:
                self.status = "串口连接失败"
                self.error = str(exc)
        finally:
            if self.serial_port:
                try:
                    self.serial_port.close()
                except (serial.SerialException, OSError):
                    pass
                self.serial_port = None

    def _record_line(self, line: str) -> None:
        wall_time = datetime.now()
        signal = parse_signal(line)
        with self.lock:
            self.raw_lines.appendleft({"time": wall_time.strftime("%H:%M:%S.%f")[:-3], "line": line})
            if not signal:
                return
            now = time.monotonic()
            if self.last_signal_monotonic is not None:
                self.longest_silence = max(self.longest_silence, now - self.last_signal_monotonic)
            self.last_signal_monotonic = now
            self.recent.append(now)
            self.total += 1
            key = signal["button"] or signal["raw"] or "unknown"
            self.button_counts[key] += 1
            event: dict[str, Any] = {
                "id": self.total,
                "time": wall_time.strftime("%H:%M:%S.%f")[:-3],
                **signal,
                "buttonCount": self.button_counts[key],
            }
            self.signals.appendleft(event)
            if self.csv_writer and self.log_file:
                self.csv_writer.writerow(
                    [
                        wall_time.isoformat(timespec="milliseconds"),
                        f"{now - self.started_monotonic:.3f}",
                        self.device,
                        signal["raw"],
                        signal["address"],
                        signal["button"],
                        signal["bits"],
                        signal["pulseUs"],
                        signal["protocol"],
                    ]
                )
                self.log_file.flush()

    def snapshot(self) -> dict[str, Any]:
        now = time.monotonic()
        with self.lock:
            while self.recent and now - self.recent[0] > 10:
                self.recent.popleft()
            silence = None if self.last_signal_monotonic is None else now - self.last_signal_monotonic
            if silence is not None:
                self.longest_silence = max(self.longest_silence, silence)
            return {
                "status": self.status,
                "error": self.error,
                "device": self.device,
                "baud": self.baud,
                "elapsed": now - self.started_monotonic,
                "total": self.total,
                "recent10": len(self.recent),
                "silence": silence,
                "longestSilence": self.longest_silence,
                "signals": list(self.signals),
                "rawLines": list(self.raw_lines),
                "logName": self.log_path.name if self.log_path else "",
            }

    def reset(self) -> None:
        with self.lock:
            self.started_monotonic = time.monotonic()
            self.last_signal_monotonic = None
            self.longest_silence = 0.0
            self.total = 0
            self.recent.clear()
            self.signals.clear()
            self.raw_lines.clear()
            self.button_counts.clear()

    def close(self) -> None:
        self.stop_event.set()
        if self.serial_port:
            try:
                self.serial_port.cancel_read()
            except (AttributeError, serial.SerialException, OSError):
                pass
        self.thread.join(timeout=2)
        if self.log_file:
            self.log_file.close()
            self.log_file = None


HTML = r"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ESP32 433MHz USB 距离测试</title>
<style>
:root{font-family:"Microsoft YaHei",system-ui,sans-serif;color:#172033;background:#eef2f7}body{margin:0}.wrap{max-width:1180px;margin:auto;padding:18px}.top{display:flex;gap:16px;align-items:center;justify-content:space-between;flex-wrap:wrap}.badge{padding:7px 12px;border-radius:20px;background:#344054;color:white}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:16px 0}.card,.panel{background:white;border-radius:12px;box-shadow:0 2px 10px #18223018;padding:15px}.metric b{display:block;font-size:30px;margin-top:6px}.flash{background:#475467;color:white;text-align:center;font-size:25px;font-weight:bold;padding:20px;border-radius:12px;transition:.15s}.flash.on{background:#079455}.actions{display:flex;gap:10px;margin:12px 0}button,a.button{border:0;border-radius:8px;padding:9px 14px;background:#175cd3;color:white;text-decoration:none;cursor:pointer;font-size:14px}table{width:100%;border-collapse:collapse;font-family:Consolas,monospace}th,td{padding:8px;border-bottom:1px solid #e4e7ec;text-align:center}th{position:sticky;top:0;background:#f9fafb}.scroll{max-height:350px;overflow:auto}.tabs{display:flex;gap:8px;margin-top:16px}.tab{background:#667085}.tab.active{background:#175cd3}.hidden{display:none}pre{white-space:pre-wrap;margin:0;font:13px Consolas,monospace}.error{color:#b42318;font-weight:bold}.note{color:#667085}.latest{margin-top:8px;font:16px Consolas,monospace}@media(max-width:760px){.metrics{grid-template-columns:repeat(2,1fr)}.wrap{padding:10px}}
</style></head><body><div class="wrap">
<div class="top"><div><h2>ESP32 433MHz USB 距离测试</h2><div class="note" id="device"></div></div><span class="badge" id="status">正在连接</span></div>
<div id="error" class="error"></div>
<div class="metrics">
 <div class="card metric">累计成功接收<b id="total">0</b></div><div class="card metric">最近 10 秒<b id="recent">0</b></div>
 <div class="card metric">当前无信号时间<b id="silence">--</b></div><div class="card metric">最长无信号时间<b id="longest">0.0 秒</b></div>
</div>
<div class="flash" id="flash">等待遥控器信号</div><div class="card latest" id="latest">时间 --　原始码 --　地址 --　按键 --</div>
<div class="actions"><button onclick="resetStats()">清零屏幕统计</button><a class="button" href="/download.csv">下载本次 CSV</a><span class="note" id="runtime"></span></div>
<div class="tabs"><button class="tab active" onclick="showTab('signals',this)">成功接收记录</button><button class="tab" onclick="showTab('raw',this)">串口原始输出</button></div>
<div class="panel scroll" id="signals"><table><thead><tr><th>时间</th><th>原始码</th><th>地址</th><th>按键</th><th>位数</th><th>脉宽 µs</th><th>按键累计</th></tr></thead><tbody id="rows"></tbody></table></div>
<div class="panel scroll hidden" id="raw"><pre id="rawText"></pre></div>
<p class="note">接收板不提供 RSSI/dBm。本页面统计成功解码结果；每个距离点建议每秒按一次，共按 20 次。</p>
</div><script>
let lastId=0;function secs(v){return v==null?'--':v.toFixed(1)+' 秒'}function elapsed(v){v=Math.floor(v);return [Math.floor(v/3600),Math.floor(v%3600/60),v%60].map(x=>String(x).padStart(2,'0')).join(':')}function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function update(){try{const d=await fetch('/api/state',{cache:'no-store'}).then(r=>r.json());status.textContent=d.status;device.textContent=d.device+' @ '+d.baud+'　日志：'+d.logName;error.textContent=d.error||'';total.textContent=d.total;recent.textContent=d.recent10;silence.textContent=secs(d.silence);longest.textContent=secs(d.longestSilence);runtime.textContent='测试时间 '+elapsed(d.elapsed);if(d.signals.length){const x=d.signals[0];latest.textContent=`时间 ${x.time}　原始码 ${x.raw||'--'}　地址 ${x.address||'--'}　按键 ${x.button||'--'}`;if(x.id!==lastId){lastId=x.id;flash.textContent='收到信号　'+(x.raw||x.button);flash.classList.add('on');setTimeout(()=>flash.classList.remove('on'),350)}}rows.innerHTML=d.signals.map(x=>`<tr><td>${esc(x.time)}</td><td>${esc(x.raw)}</td><td>${esc(x.address)}</td><td>${esc(x.button)}</td><td>${esc(x.bits)}</td><td>${esc(x.pulseUs)}</td><td>${esc(x.buttonCount)}</td></tr>`).join('');rawText.textContent=d.rawLines.map(x=>x.time+'  '+x.line).join('\n')}catch(e){status.textContent='网页连接中断';error.textContent=String(e)}}
function showTab(id,b){document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));b.classList.add('active');signals.classList.toggle('hidden',id!=='signals');raw.classList.toggle('hidden',id!=='raw')}
async function resetStats(){await fetch('/api/reset',{method:'POST'});lastId=0;flash.textContent='等待遥控器信号';latest.textContent='时间 --　原始码 --　地址 --　按键 --';update()}setInterval(update,250);update();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    monitor: Monitor

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _send(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._send(HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/api/state":
            self._send(json.dumps(self.monitor.snapshot(), ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
        elif path == "/download.csv" and self.monitor.log_path and self.monitor.log_path.exists():
            self._send(self.monitor.log_path.read_bytes(), "text/csv; charset=utf-8")
        else:
            self._send(b"Not found", "text/plain", HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if urlparse(self.path).path == "/api/reset":
            self.monitor.reset()
            self._send(b'{"ok":true}', "application/json")
        else:
            self._send(b"Not found", "text/plain", HTTPStatus.NOT_FOUND)


def main() -> int:
    parser = argparse.ArgumentParser(description="ESP32 USB RF range-test web server")
    parser.add_argument("--device", default="", help="serial device; auto-detected when omitted")
    parser.add_argument("--baud", type=int, default=BAUD)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    monitor = Monitor(choose_device(args.device), args.baud)
    Handler.monitor = monitor
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    monitor.start()
    print(f"ESP32 USB range-test page: http://{args.host}:{args.port}", flush=True)
    print(f"Serial device: {monitor.device} @ {monitor.baud}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        monitor.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
