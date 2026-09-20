#!/usr/bin/env python3
"""GUI range test tool for the Gateball ESP32 433 MHz USB bridge."""

from __future__ import annotations

import argparse
import csv
import json
import queue
import sys
import threading
import time
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import tkinter as tk
    from tkinter import messagebox, ttk
except ImportError as exc:  # pragma: no cover - depends on OS package selection
    raise SystemExit("缺少 Tk 图形库。Ubuntu 请安装 python3-tk。") from exc

try:
    import serial
    from serial.tools import list_ports
except ImportError as exc:
    raise SystemExit(
        "缺少 pyserial。请运行：python -m pip install pyserial"
    ) from exc


DEFAULT_BAUD = 115200
MAX_LOG_ROWS = 1000


@dataclass(frozen=True)
class Signal:
    received_at: datetime
    raw: str
    address: str
    button: str
    bits: str
    pulse_us: str
    protocol: str
    source_line: str


def parse_signal(line: str) -> Signal | None:
    """Parse the JSON line emitted by esp32_433_bridge.ino."""
    text = line.strip()
    if text.startswith("RFJSON:"):
        text = text.removeprefix("RFJSON:").strip()
    if not text.startswith("{"):
        return None
    try:
        data: dict[str, Any] = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    if not any(data.get(key) for key in ("raw", "address", "button")):
        return None
    return Signal(
        received_at=datetime.now(),
        raw=str(data.get("raw") or data.get("code") or ""),
        address=str(data.get("address") or ""),
        button=str(data.get("button") or ""),
        bits=str(data.get("bits") or ""),
        pulse_us=str(data.get("pulseUs") or ""),
        protocol=str(data.get("protocol") or ""),
        source_line=line.rstrip("\r\n"),
    )


def port_score(port: Any) -> tuple[int, str]:
    text = " ".join(
        str(value or "")
        for value in (port.device, port.description, port.manufacturer, port.hwid)
    ).lower()
    score = 0
    for marker, points in (
        ("cp210", 100),
        ("silicon labs", 100),
        ("usb to uart", 80),
        ("usb-to-uart", 80),
        ("ch340", 70),
        ("ch341", 70),
        ("ftdi", 60),
        ("usb", 20),
    ):
        if marker in text:
            score += points
    return (-score, str(port.device))


class RangeTestApp:
    def __init__(self, root: tk.Tk, preferred_port: str = "", baud: int = DEFAULT_BAUD) -> None:
        self.root = root
        self.root.title("ESP32 433MHz USB 距离测试")
        self.root.geometry("1060x720")
        self.root.minsize(900, 620)

        self.serial_port: serial.Serial | None = None
        self.reader_thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.recent_signals: deque[float] = deque()
        self.button_counts: Counter[str] = Counter()
        self.started_at: float | None = None
        self.last_signal_at: float | None = None
        self.total_signals = 0
        self.longest_silence = 0.0
        self.log_file = None
        self.csv_writer: csv.writer | None = None
        self.port_labels: dict[str, str] = {}

        self.port_var = tk.StringVar(value=preferred_port)
        self.baud_var = tk.StringVar(value=str(baud))
        self.status_var = tk.StringVar(value="未连接")
        self.elapsed_var = tk.StringVar(value="00:00:00")
        self.total_var = tk.StringVar(value="0")
        self.recent_var = tk.StringVar(value="0")
        self.silence_var = tk.StringVar(value="--")
        self.longest_silence_var = tk.StringVar(value="0.0 秒")
        self.last_time_var = tk.StringVar(value="--")
        self.last_raw_var = tk.StringVar(value="--")
        self.last_address_var = tk.StringVar(value="--")
        self.last_button_var = tk.StringVar(value="--")
        self.last_detail_var = tk.StringVar(value="等待遥控器信号")
        self.log_path_var = tk.StringVar(value="开始测试后自动生成 CSV 日志")

        self._build_ui()
        self.refresh_ports(select_preferred=preferred_port)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(100, self._drain_events)
        self.root.after(250, self._update_clock)

    def _build_ui(self) -> None:
        style = ttk.Style()
        style.configure("Metric.TLabel", font=("Microsoft YaHei UI", 22, "bold"))
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 15, "bold"))

        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill="both", expand=True)

        connect = ttk.LabelFrame(outer, text="USB 串口", padding=10)
        connect.pack(fill="x")
        ttk.Label(connect, text="设备：").pack(side="left")
        self.port_combo = ttk.Combobox(connect, textvariable=self.port_var, width=52)
        self.port_combo.pack(side="left", padx=(0, 8))
        ttk.Button(connect, text="刷新", command=self.refresh_ports).pack(side="left", padx=(0, 10))
        ttk.Label(connect, text="波特率：").pack(side="left")
        ttk.Entry(connect, textvariable=self.baud_var, width=9).pack(side="left", padx=(0, 10))
        self.connect_button = ttk.Button(connect, text="开始测试", command=self.toggle_connection)
        self.connect_button.pack(side="left")
        ttk.Button(connect, text="清零统计", command=self.reset_statistics).pack(side="left", padx=8)

        status = ttk.Frame(outer, padding=(2, 12, 2, 8))
        status.pack(fill="x")
        ttk.Label(status, textvariable=self.status_var, style="Title.TLabel").pack(side="left")
        ttk.Label(status, text="测试时间：").pack(side="left", padx=(35, 3))
        ttk.Label(status, textvariable=self.elapsed_var).pack(side="left")
        ttk.Label(status, textvariable=self.log_path_var).pack(side="right")

        metrics = ttk.Frame(outer)
        metrics.pack(fill="x", pady=(0, 10))
        for column in range(4):
            metrics.columnconfigure(column, weight=1)
        self._metric(metrics, 0, "累计成功接收", self.total_var)
        self._metric(metrics, 1, "最近 10 秒", self.recent_var)
        self._metric(metrics, 2, "当前无信号时间", self.silence_var)
        self._metric(metrics, 3, "最长无信号时间", self.longest_silence_var)

        latest = ttk.LabelFrame(outer, text="最后一次成功解码", padding=12)
        latest.pack(fill="x", pady=(0, 10))
        latest.columnconfigure(1, weight=1)
        self.flash_label = tk.Label(
            latest,
            textvariable=self.last_detail_var,
            bg="#444444",
            fg="white",
            font=("Microsoft YaHei UI", 19, "bold"),
            padx=12,
            pady=12,
        )
        self.flash_label.grid(row=0, column=0, columnspan=6, sticky="ew", pady=(0, 10))
        labels = (
            ("时间", self.last_time_var),
            ("原始码", self.last_raw_var),
            ("地址", self.last_address_var),
            ("按键", self.last_button_var),
        )
        for index, (title, variable) in enumerate(labels):
            ttk.Label(latest, text=f"{title}：").grid(row=1, column=index * 2, sticky="e", padx=(8, 3))
            ttk.Label(latest, textvariable=variable, font=("Consolas", 11, "bold")).grid(
                row=1, column=index * 2 + 1, sticky="w", padx=(0, 12)
            )

        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True)

        signal_frame = ttk.Frame(notebook, padding=6)
        raw_frame = ttk.Frame(notebook, padding=6)
        notebook.add(signal_frame, text="成功接收记录")
        notebook.add(raw_frame, text="串口原始输出")

        columns = ("time", "raw", "address", "button", "bits", "pulse", "count")
        self.tree = ttk.Treeview(signal_frame, columns=columns, show="headings", height=14)
        headings = ("时间", "原始码", "地址", "按键", "位数", "脉宽 µs", "该按键累计")
        widths = (125, 145, 120, 100, 65, 90, 105)
        for column, heading, width in zip(columns, headings, widths):
            self.tree.heading(column, text=heading)
            self.tree.column(column, width=width, anchor="center")
        scrollbar = ttk.Scrollbar(signal_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.raw_text = tk.Text(raw_frame, wrap="none", font=("Consolas", 10), state="disabled")
        raw_scroll = ttk.Scrollbar(raw_frame, orient="vertical", command=self.raw_text.yview)
        self.raw_text.configure(yscrollcommand=raw_scroll.set)
        self.raw_text.pack(side="left", fill="both", expand=True)
        raw_scroll.pack(side="right", fill="y")

        note = (
            "说明：该接收板不提供 RSSI/dBm。本工具统计的是成功解码结果。"
            "距离测试时请用相同姿势、相同按键频率进行比较。"
        )
        ttk.Label(outer, text=note, foreground="#555555").pack(fill="x", pady=(8, 0))

    @staticmethod
    def _metric(parent: ttk.Frame, column: int, title: str, variable: tk.StringVar) -> None:
        frame = ttk.LabelFrame(parent, text=title, padding=10)
        frame.grid(row=0, column=column, sticky="nsew", padx=4)
        ttk.Label(frame, textvariable=variable, style="Metric.TLabel").pack()

    def refresh_ports(self, select_preferred: str = "") -> None:
        ports = sorted(list(list_ports.comports()), key=port_score)
        self.port_labels.clear()
        values = []
        for port in ports:
            label = f"{port.device} — {port.description or '串口设备'}"
            self.port_labels[label] = port.device
            values.append(label)
        self.port_combo["values"] = values

        current = select_preferred or self._selected_device()
        if current:
            match = next((label for label, device in self.port_labels.items() if device == current), None)
            self.port_var.set(match or current)
        elif values and not self.serial_port:
            self.port_var.set(values[0])

    def _selected_device(self) -> str:
        value = self.port_var.get().strip()
        return self.port_labels.get(value, value.split(" — ", 1)[0].strip())

    def toggle_connection(self) -> None:
        if self.serial_port:
            self.disconnect()
        else:
            self.connect()

    def connect(self) -> None:
        device = self._selected_device()
        if not device:
            messagebox.showwarning("没有串口", "请连接 ESP32，然后点击刷新。")
            return
        try:
            baud = int(self.baud_var.get())
            self.serial_port = serial.Serial(device, baudrate=baud, timeout=0.25)
        except (ValueError, serial.SerialException, OSError) as exc:
            self.serial_port = None
            messagebox.showerror("连接失败", f"无法打开 {device}\n\n{exc}\n\n请关闭占用此串口的程序。")
            return

        self.reset_statistics()
        self.started_at = time.monotonic()
        self.stop_event.clear()
        self._open_log(device)
        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader_thread.start()
        self.status_var.set(f"已连接：{device} @ {baud}")
        self.connect_button.configure(text="停止测试")

    def disconnect(self) -> None:
        self.stop_event.set()
        port = self.serial_port
        self.serial_port = None
        if port:
            try:
                port.close()
            except (serial.SerialException, OSError):
                pass
        if self.log_file:
            self.log_file.close()
            self.log_file = None
            self.csv_writer = None
        self.status_var.set("已停止")
        self.connect_button.configure(text="开始测试")

    def _open_log(self, device: str) -> None:
        log_dir = Path(__file__).resolve().parent / "logs"
        log_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = log_dir / f"range-test-{stamp}.csv"
        self.log_file = path.open("w", newline="", encoding="utf-8-sig")
        self.csv_writer = csv.writer(self.log_file)
        self.csv_writer.writerow(
            ["time", "elapsed_seconds", "port", "raw", "address", "button", "bits", "pulse_us", "protocol"]
        )
        self.log_file.flush()
        self.log_path_var.set(f"日志：{path.name}")

    def _reader_loop(self) -> None:
        while not self.stop_event.is_set():
            port = self.serial_port
            if not port:
                return
            try:
                raw = port.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                if line:
                    self.events.put(("line", line))
            except (serial.SerialException, OSError) as exc:
                self.events.put(("error", str(exc)))
                return

    def _drain_events(self) -> None:
        try:
            while True:
                event_type, payload = self.events.get_nowait()
                if event_type == "line":
                    self._append_raw(payload)
                    signal = parse_signal(payload)
                    if signal:
                        self._record_signal(signal)
                elif event_type == "error":
                    messagebox.showerror("串口已断开", str(payload))
                    self.disconnect()
        except queue.Empty:
            pass
        self.root.after(100, self._drain_events)

    def _append_raw(self, line: str) -> None:
        self.raw_text.configure(state="normal")
        self.raw_text.insert("end", f"{datetime.now():%H:%M:%S.%f}"[:-3] + f"  {line}\n")
        line_count = int(self.raw_text.index("end-1c").split(".")[0])
        if line_count > MAX_LOG_ROWS:
            self.raw_text.delete("1.0", f"{line_count - MAX_LOG_ROWS}.0")
        self.raw_text.see("end")
        self.raw_text.configure(state="disabled")

    def _record_signal(self, signal: Signal) -> None:
        now = time.monotonic()
        self.total_signals += 1
        self.recent_signals.append(now)
        key = signal.button or signal.raw or "unknown"
        self.button_counts[key] += 1

        if self.last_signal_at is not None:
            self.longest_silence = max(self.longest_silence, now - self.last_signal_at)
        self.last_signal_at = now

        self.total_var.set(str(self.total_signals))
        self.last_time_var.set(signal.received_at.strftime("%H:%M:%S.%f")[:-3])
        self.last_raw_var.set(signal.raw or "--")
        self.last_address_var.set(signal.address or "--")
        self.last_button_var.set(signal.button or "--")
        self.last_detail_var.set(f"收到信号  {signal.raw or signal.button}")
        self.flash_label.configure(bg="#11823b")
        self.root.after(350, lambda: self.flash_label.configure(bg="#444444"))

        self.tree.insert(
            "",
            0,
            values=(
                signal.received_at.strftime("%H:%M:%S.%f")[:-3],
                signal.raw,
                signal.address,
                signal.button,
                signal.bits,
                signal.pulse_us,
                self.button_counts[key],
            ),
        )
        rows = self.tree.get_children()
        if len(rows) > MAX_LOG_ROWS:
            self.tree.delete(*rows[MAX_LOG_ROWS:])

        if self.csv_writer and self.log_file:
            elapsed = now - self.started_at if self.started_at is not None else 0.0
            self.csv_writer.writerow(
                [
                    signal.received_at.isoformat(timespec="milliseconds"),
                    f"{elapsed:.3f}",
                    self._selected_device(),
                    signal.raw,
                    signal.address,
                    signal.button,
                    signal.bits,
                    signal.pulse_us,
                    signal.protocol,
                ]
            )
            self.log_file.flush()

    def _update_clock(self) -> None:
        now = time.monotonic()
        while self.recent_signals and now - self.recent_signals[0] > 10:
            self.recent_signals.popleft()
        self.recent_var.set(str(len(self.recent_signals)))

        if self.started_at is not None:
            elapsed = max(0, int(now - self.started_at))
            hours, remainder = divmod(elapsed, 3600)
            minutes, seconds = divmod(remainder, 60)
            self.elapsed_var.set(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        if self.last_signal_at is not None:
            silence = now - self.last_signal_at
            self.silence_var.set(f"{silence:.1f} 秒")
            self.longest_silence = max(self.longest_silence, silence)
            self.longest_silence_var.set(f"{self.longest_silence:.1f} 秒")
        self.root.after(250, self._update_clock)

    def reset_statistics(self) -> None:
        self.started_at = time.monotonic() if self.serial_port else None
        self.last_signal_at = None
        self.total_signals = 0
        self.longest_silence = 0.0
        self.recent_signals.clear()
        self.button_counts.clear()
        self.total_var.set("0")
        self.recent_var.set("0")
        self.elapsed_var.set("00:00:00")
        self.silence_var.set("--")
        self.longest_silence_var.set("0.0 秒")
        self.last_time_var.set("--")
        self.last_raw_var.set("--")
        self.last_address_var.set("--")
        self.last_button_var.set("--")
        self.last_detail_var.set("等待遥控器信号")
        for row in self.tree.get_children():
            self.tree.delete(row)

    def close(self) -> None:
        self.disconnect()
        self.root.destroy()


def main() -> int:
    parser = argparse.ArgumentParser(description="ESP32 433 MHz USB range test")
    parser.add_argument("--port", default="", help="serial device, for example COM5 or /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    args = parser.parse_args()

    root = tk.Tk()
    RangeTestApp(root, preferred_port=args.port, baud=args.baud)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
