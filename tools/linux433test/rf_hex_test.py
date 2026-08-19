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
from dataclasses import dataclass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="433MHz GPIO hex code test")
    parser.add_argument("--gpio", type=int, required=True, help="BCM GPIO number connected to receiver DATA")
    parser.add_argument(
        "--backend",
        choices=("auto", "rpi-rf", "lgpio", "rpi-gpio"),
        default="auto",
        help="GPIO backend. Use lgpio to bypass rpi-rf and decode raw GPIO edges.",
    )
    parser.add_argument("--debounce-ms", type=int, default=300, help="Ignore repeated decoded codes in this window")
    parser.add_argument("--gap-us", type=int, default=6000, help="Pulse gap that marks a raw frame boundary")
    parser.add_argument("--min-pulses", type=int, default=24, help="Minimum raw pulses before printing fallback data")
    parser.add_argument(
        "--dump-pulses",
        type=int,
        default=0,
        help="Print and clear every N raw pulses even if no frame gap is detected. Useful when decoding fails.",
    )
    return parser.parse_args()


@dataclass(frozen=True)
class Frame:
    code: int
    short_us: float
    long_us: float


class PWM24Decoder:
    SYNC_MIN_US = 8_000
    SYNC_MAX_US = 18_000
    SHORT_MIN_US = 180
    SHORT_MAX_US = 700
    LONG_MIN_US = 800
    LONG_MAX_US = 1_700

    def __init__(self) -> None:
        self._collecting = False
        self._runs: list[tuple[int, float]] = []

    def feed_transition(self, finished_level: int, duration_us: float, new_level: int) -> Frame | None:
        if (
            finished_level == 0
            and new_level == 1
            and self.SYNC_MIN_US <= duration_us <= self.SYNC_MAX_US
        ):
            self._collecting = True
            self._runs = []
            return None

        if not self._collecting:
            return None

        self._runs.append((finished_level, duration_us))
        if len(self._runs) < 48:
            return None

        runs = self._runs
        self._collecting = False
        self._runs = []
        return self._decode_runs(runs)

    def _decode_runs(self, runs: list[tuple[int, float]]) -> Frame | None:
        bits: list[str] = []
        shorts: list[float] = []
        longs: list[float] = []
        for i in range(0, 48, 2):
            high_level, high_us = runs[i]
            low_level, low_us = runs[i + 1]
            if high_level != 1 or low_level != 0:
                return None

            high_short = self.SHORT_MIN_US <= high_us <= self.SHORT_MAX_US
            low_short = self.SHORT_MIN_US <= low_us <= self.SHORT_MAX_US
            high_long = self.LONG_MIN_US <= high_us <= self.LONG_MAX_US
            low_long = self.LONG_MIN_US <= low_us <= self.LONG_MAX_US

            if high_short and low_long:
                bits.append("0")
                shorts.append(high_us)
                longs.append(low_us)
            elif high_long and low_short:
                bits.append("1")
                longs.append(high_us)
                shorts.append(low_us)
            else:
                return None

        return Frame(code=int("".join(bits), 2), short_us=sum(shorts) / len(shorts), long_us=sum(longs) / len(longs))


class RepeatFilter:
    def __init__(self, repeats_required: int = 2, repeat_window_s: float = 0.25):
        self.repeats_required = repeats_required
        self.repeat_window_s = repeat_window_s
        self._candidate: int | None = None
        self._count = 0
        self._last_frame_time = 0.0
        self._emitted = False

    def accept(self, frame: Frame) -> bool:
        now = time.monotonic()
        same_group = frame.code == self._candidate and now - self._last_frame_time <= self.repeat_window_s
        if same_group:
            self._count += 1
        else:
            self._candidate = frame.code
            self._count = 1
            self._emitted = False
        self._last_frame_time = now
        if self._count >= self.repeats_required and not self._emitted:
            self._emitted = True
            return True
        return False


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


def split_rf_code(code: int) -> tuple[int, int]:
    return (code >> 8) & 0xFFFF, code & 0xFF


def print_decoded_frame(frame: Frame, *, prefix: str, debounce_ms: int, state: dict[str, float | int | None]) -> None:
    now = time.monotonic()
    last_code = state.get("last_code")
    last_at = float(state.get("last_at") or 0.0)
    if frame.code == last_code and (now - last_at) * 1000 < debounce_ms:
        return
    address, button = split_rf_code(frame.code)
    print(
        f"{prefix} code=0x{frame.code:06X} hex={int_to_hex_bytes(frame.code)} "
        f"address=0x{address:04X} button=0x{button:02X} "
        f"short_us={frame.short_us:.0f} long_us={frame.long_us:.0f}",
        flush=True,
    )
    state["last_code"] = frame.code
    state["last_at"] = now


def run_rpi_rf(gpio: int, debounce_ms: int) -> bool:
    try:
        from rpi_rf import RFDevice  # type: ignore
    except ImportError:
        return False

    try:
        rfdevice = RFDevice(gpio)
        rfdevice.enable_rx()
    except Exception as exc:
        print(f"rpi-rf cannot start on this Raspberry Pi: {exc}")
        return False
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


def run_lgpio(gpio: int, gap_us: int, min_pulses: int, dump_pulses: int) -> bool:
    try:
        import lgpio  # type: ignore
    except ImportError:
        return False

    try:
        handle = lgpio.gpiochip_open(0)
        lgpio.gpio_claim_input(handle, gpio)
    except Exception as exc:
        print(f"lgpio cannot open BCM GPIO {gpio}: {exc}")
        return False
    pulses: deque[tuple[int, int]] = deque(maxlen=512)
    decoder = PWM24Decoder()
    inverted_decoder = PWM24Decoder()
    repeat_filter = RepeatFilter()
    inverted_repeat_filter = RepeatFilter()
    decoded_state: dict[str, float | int | None] = {"last_code": None, "last_at": 0.0}
    last_tick = None
    last_level = None

    def on_edge(_chip: int, _gpio: int, level: int, tick: int) -> None:
        nonlocal last_tick, last_level
        if last_tick is None:
            last_tick = tick
            last_level = int(level)
            return
        duration = int((tick - last_tick) & 0xFFFFFFFF)
        finished_level = int(last_level if last_level is not None else 1 - int(level))
        last_tick = tick
        last_level = int(level)
        frame = decoder.feed_transition(finished_level, duration, int(level))
        if frame is not None and repeat_filter.accept(frame):
            print_decoded_frame(frame, prefix="decoded", debounce_ms=300, state=decoded_state)
        inverted_frame = inverted_decoder.feed_transition(1 - finished_level, duration, 1 - int(level))
        if inverted_frame is not None and inverted_repeat_filter.accept(inverted_frame):
            print_decoded_frame(inverted_frame, prefix="decoded-inverted", debounce_ms=300, state=decoded_state)
        if duration >= gap_us:
            if len(pulses) >= min_pulses:
                print(summarize_pulse_frame(list(pulses)))
            pulses.clear()
        else:
            pulses.append((int(level), duration))
            if dump_pulses > 0 and len(pulses) >= dump_pulses:
                print("dump " + summarize_pulse_frame(list(pulses)), flush=True)
                pulses.clear()

    callback = lgpio.callback(handle, gpio, lgpio.BOTH_EDGES, on_edge)
    print(f"Listening with lgpio on BCM GPIO {gpio}. Press Ctrl+C to stop.")
    print("It will print decoded 24-bit PWM codes when possible, plus raw pulse frames for discovery.")
    if dump_pulses > 0:
        print(f"Raw pulse dump enabled: every {dump_pulses} pulses.")
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

    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(gpio, GPIO.IN)
    except Exception as exc:
        print(f"RPi.GPIO cannot start on this Raspberry Pi: {exc}")
        return False
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
    print(f"Backend: {args.backend}")
    print(f"Decimal text hex example: {text_to_hex_bytes(str(args.gpio))}")
    if args.backend in ("auto", "rpi-rf") and run_rpi_rf(args.gpio, args.debounce_ms):
        return 0
    if args.backend in ("auto", "lgpio") and run_lgpio(args.gpio, args.gap_us, args.min_pulses, args.dump_pulses):
        return 0
    if args.backend in ("auto", "rpi-gpio") and run_rpi_gpio(args.gpio, args.gap_us, args.min_pulses):
        return 0
    print("No supported library found.")
    print("Install decoder: sudo apt install -y python3-pip python3-rpi.gpio python3-lgpio")
    print("Then: sudo python3 -m pip install rpi-rf --break-system-packages")
    print("For Windows-like GPIO edge decoding, run: python3 rf_hex_test.py --gpio 17 --backend lgpio")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
