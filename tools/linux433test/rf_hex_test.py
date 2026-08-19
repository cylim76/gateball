#!/usr/bin/env python3
"""Read a 433MHz receiver on Raspberry Pi GPIO and print decoded codes as hex.

The preferred decoder is rpi-rf. If rpi-rf is unavailable, the script falls back
to pulse capture through lgpio or RPi.GPIO so you can at least confirm that the
DATA pin is receiving transitions.
"""

from __future__ import annotations

import argparse
import statistics
import time
from collections import deque


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="433MHz GPIO hex code test")
    parser.add_argument("--gpio", type=int, required=True, help="BCM GPIO number connected to receiver DATA")
    parser.add_argument("--debounce-ms", type=int, default=300, help="Ignore repeated decoded codes in this window")
    parser.add_argument("--gap-us", type=int, default=6000, help="Pulse gap that marks a raw frame boundary")
    parser.add_argument("--min-pulses", type=int, default=24, help="Minimum raw pulses before printing fallback data")
    return parser.parse_args()


def int_to_hex_bytes(value: int) -> str:
    if value < 0:
        value = 0
    width = max(1, (value.bit_length() + 7) // 8)
    return " ".join(f"{byte:02X}" for byte in value.to_bytes(width, "big"))


def text_to_hex_bytes(text: str) -> str:
    return " ".join(f"{byte:02X}" for byte in text.encode("utf-8", errors="replace"))


def split_address_button(code: int | str) -> tuple[str, str]:
    text = str(code)
    if len(text) <= 1:
        return text, ""
    return text[:-1], text[-1]


def run_rpi_rf(gpio: int, debounce_ms: int) -> bool:
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
    print("Press a remote button...")
    try:
        while True:
            timestamp = rfdevice.rx_code_timestamp
            if timestamp and timestamp != last_timestamp:
                last_timestamp = timestamp
                now = time.monotonic()
                code = int(rfdevice.rx_code)
                if code != last_code or (now - last_at) * 1000 >= debounce_ms:
                    address, button = split_address_button(code)
                    print(
                        "code={code} hex={hex_code} address={address} button={button} protocol={protocol} pulse={pulse}".format(
                            code=code,
                            hex_code=int_to_hex_bytes(code),
                            address=address,
                            button=button or "-",
                            protocol=rfdevice.rx_proto,
                            pulse=rfdevice.rx_pulselength,
                        )
                    )
                    last_code = code
                    last_at = now
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        rfdevice.cleanup()
    return True


def summarize_pulse_frame(pulses: list[tuple[int, int]]) -> str:
    durations = [duration for _, duration in pulses if 50 <= duration <= 20000]
    if not durations:
        return "raw pulses received, but no usable durations"
    median = int(statistics.median(durations))
    compact = []
    for level, duration in pulses[:96]:
        bucket = max(0, min(255, round(duration / 50)))
        compact.append(level & 1)
        compact.append(bucket)
    raw_hex = " ".join(f"{value:02X}" for value in compact)
    sample = " ".join(f"{level}:{duration}" for level, duration in pulses[:32])
    return f"raw-frame pulses={len(pulses)} median_us={median} hex={raw_hex} sample={sample}"


def run_lgpio(gpio: int, gap_us: int, min_pulses: int) -> bool:
    try:
        import lgpio  # type: ignore
    except ImportError:
        return False

    handle = lgpio.gpiochip_open(0)
    lgpio.gpio_claim_input(handle, gpio)
    pulses: deque[tuple[int, int]] = deque(maxlen=512)
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
                print(summarize_pulse_frame(list(pulses)))
            pulses.clear()
        else:
            pulses.append((int(level), duration))

    callback = lgpio.callback(handle, gpio, lgpio.BOTH_EDGES, on_edge)
    print(f"rpi-rf not found. Listening raw pulses with lgpio on BCM GPIO {gpio}.")
    print("This confirms signal activity, but it is not a decoded remote code.")
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
    pulses: deque[tuple[int, int]] = deque(maxlen=512)
    last_ns = time.monotonic_ns()
    last_level = GPIO.input(gpio)
    print(f"rpi-rf/lgpio not found. Polling raw pulses with RPi.GPIO on BCM GPIO {gpio}.")
    print("This confirms signal activity, but it is not a decoded remote code.")
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
                        print(summarize_pulse_frame(list(pulses)))
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
    print(f"GPIO: BCM {args.gpio}")
    print(f"Decimal text hex example: {text_to_hex_bytes(str(args.gpio))}")
    if run_rpi_rf(args.gpio, args.debounce_ms):
        return 0
    if run_lgpio(args.gpio, args.gap_us, args.min_pulses):
        return 0
    if run_rpi_gpio(args.gpio, args.gap_us, args.min_pulses):
        return 0
    print("No supported library found.")
    print("Install decoder: sudo apt install -y python3-pip python3-rpi.gpio")
    print("Then: sudo python3 -m pip install rpi-rf --break-system-packages")
    print("Or raw pulse fallback: sudo apt install -y python3-lgpio")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
