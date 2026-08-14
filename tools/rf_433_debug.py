#!/usr/bin/env python3
"""Debug a 433MHz OOK/ASK receiver connected to Raspberry Pi GPIO.

Preferred path:
  pip install rpi-rf
  python3 tools/rf_433_debug.py --gpio 27

Fallback path prints pulse frames through lgpio or RPi.GPIO when rpi-rf is not
installed. The fallback is for discovery, not a full protocol decoder.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import deque
from urllib import request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Debug 433MHz RF remote codes")
    parser.add_argument("--gpio", type=int, default=27, help="BCM GPIO number connected to receiver DATA")
    parser.add_argument("--debounce-ms", type=int, default=300, help="Ignore duplicate decoded codes within this window")
    parser.add_argument("--gap-us", type=int, default=6000, help="Pulse gap that marks the end of a fallback frame")
    parser.add_argument("--min-pulses", type=int, default=24, help="Minimum fallback pulses before a frame is printed")
    parser.add_argument(
        "--post-url",
        default="",
        help="Optional scoreboard action URL, for example http://127.0.0.1:8000/api/action",
    )
    return parser.parse_args()


def split_address_button(code: int | str) -> tuple[str, str]:
    text = str(code)
    if len(text) <= 1:
        return text, ""
    return text[:-1], text[-1]


def post_signal(post_url: str, *, code: int | str, address: str, button: str) -> None:
    if not post_url:
        return
    payload = json.dumps(
        {
            "action": "simulate_rf_signal",
            "raw": str(code),
            "address": address,
            "button": button,
        }
    ).encode("utf-8")
    req = request.Request(post_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with request.urlopen(req, timeout=1.5) as response:
            status = response.status
            body = response.read().decode("utf-8", errors="replace")
        print(f"posted status={status} response={body[:160]}")
    except Exception as exc:
        print(f"post failed: {exc}")


def run_rpi_rf(gpio: int, debounce_ms: int, post_url: str) -> bool:
    try:
        from rpi_rf import RFDevice  # type: ignore
    except ImportError:
        return False

    rfdevice = RFDevice(gpio)
    rfdevice.enable_rx()
    last_timestamp = None
    last_code = None
    last_at = 0.0
    print(f"Listening with rpi-rf on BCM GPIO {gpio}. Press Ctrl+C to stop.")
    try:
        while True:
            timestamp = rfdevice.rx_code_timestamp
            if timestamp and timestamp != last_timestamp:
                last_timestamp = timestamp
                now = time.monotonic()
                code = rfdevice.rx_code
                if code != last_code or (now - last_at) * 1000 >= debounce_ms:
                    address, button = split_address_button(code)
                    print(
                        "code={code} address={address} button={button} protocol={protocol} pulse={pulse}".format(
                            code=code,
                            address=address,
                            button=button or "-",
                            protocol=rfdevice.rx_proto,
                            pulse=rfdevice.rx_pulselength,
                        )
                    )
                    post_signal(post_url, code=code, address=address, button=button)
                    last_code = code
                    last_at = now
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        rfdevice.cleanup()
    return True


def summarize_pulses(pulses: list[tuple[int, int]]) -> str:
    durations = [duration for _, duration in pulses if 80 <= duration <= 10000]
    if not durations:
        return "no usable pulses"
    median = int(statistics.median(durations))
    sample = " ".join(f"{level}:{duration}" for level, duration in pulses[:48])
    return f"pulses={len(pulses)} median_us={median} sample={sample}"


def run_lgpio(gpio: int, gap_us: int, min_pulses: int) -> bool:
    try:
        import lgpio  # type: ignore
    except ImportError:
        return False

    handle = lgpio.gpiochip_open(0)
    lgpio.gpio_claim_input(handle, gpio)
    pulses: deque[tuple[int, int]] = deque(maxlen=256)
    last_tick = None

    def on_edge(_chip: int, _gpio: int, level: int, tick: int) -> None:
        nonlocal last_tick
        if last_tick is None:
            last_tick = tick
            return
        duration = int((tick - last_tick) & 0xFFFFFFFF)
        last_tick = tick
        if duration >= gap_us:
            if len(pulses) >= min_pulses:
                print(summarize_pulses(list(pulses)))
            pulses.clear()
        else:
            pulses.append((level, duration))

    callback = lgpio.callback(handle, gpio, lgpio.BOTH_EDGES, on_edge)
    print(f"Listening with lgpio edge capture on BCM GPIO {gpio}. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        callback.cancel()
        lgpio.gpiochip_close(handle)
    return True


def run_rpi_gpio(gpio: int, gap_us: int, min_pulses: int) -> bool:
    try:
        import RPi.GPIO as GPIO  # type: ignore
    except ImportError:
        return False

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(gpio, GPIO.IN)
    pulses: deque[tuple[int, int]] = deque(maxlen=256)
    last_ns = time.monotonic_ns()
    last_level = GPIO.input(gpio)
    print(f"Listening with RPi.GPIO polling on BCM GPIO {gpio}. Press Ctrl+C to stop.")
    try:
        while True:
            level = GPIO.input(gpio)
            if level != last_level:
                now_ns = time.monotonic_ns()
                duration_us = int((now_ns - last_ns) / 1000)
                last_ns = now_ns
                last_level = level
                if duration_us >= gap_us:
                    if len(pulses) >= min_pulses:
                        print(summarize_pulses(list(pulses)))
                    pulses.clear()
                else:
                    pulses.append((int(level), duration_us))
            time.sleep(0.00005)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        GPIO.cleanup()
    return True


def main() -> int:
    args = parse_args()
    if run_rpi_rf(args.gpio, args.debounce_ms, args.post_url):
        return 0
    if run_lgpio(args.gpio, args.gap_us, args.min_pulses):
        return 0
    if run_rpi_gpio(args.gpio, args.gap_us, args.min_pulses):
        return 0
    print("No supported GPIO library found. Try: pip install rpi-rf or sudo apt install python3-lgpio")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
