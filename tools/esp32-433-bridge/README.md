# ESP32 433MHz RF Bridge

This sketch captures OOK/ASK 433MHz receiver pulses on an ESP32 and prints
decoded remote codes over USB serial. It is meant for Gateball remote debugging
and can also be used as a serial receiver by the Gateball scoreboard.

## Wiring

Use a 433MHz OOK/ASK receiver module whose DATA output is safe for 3.3V logic.

```text
Receiver VCC  -> ESP32 3V3 or 5V, depending on the receiver module
Receiver GND  -> ESP32 GND
Receiver DATA -> ESP32 GPIO27 by default
```

If your receiver DATA output is 5V, do not connect it directly to ESP32 GPIO.
Use a level shifter or resistor divider.

## Build With PlatformIO

```bash
cd tools/esp32-433-bridge
pio run -t upload
pio device monitor -b 115200
```

To use another input pin, edit `platformio.ini`:

```ini
build_flags =
  -D RF_DATA_PIN=18
```

## Arduino IDE

Open:

```text
tools/esp32-433-bridge/esp32_433_bridge/esp32_433_bridge.ino
```

Select an ESP32 board, set baud rate to `115200`, then upload.

## Output

Stable decoded frames print a machine-readable JSON line:

```text
{"raw":"0x00553C","address":"0x0055","button":"0x3C","bits":24,"protocol":"pwm","polarity":"normal","pulseUs":107}
```

Gateball's USB serial receiver accepts this JSON line directly. In the settings
page, choose USB serial receiver and set the serial device such as:

```text
/dev/ttyUSB0
/dev/ttyACM0
```

The sketch also prints candidate and raw pulse lines for debugging. If no JSON
appears, copy the `raw` and `candidate` lines for analysis.

## Decoder Coverage

The decoder intentionally tries several common variants:

- Normal and inverted input polarity.
- Short-high/long-low and long-high/short-low PWM bit mapping.
- Reversed bit order.
- 12 to 32 bit frame lengths, with 24-bit frames preferred.
- A short address-prefix frame can be repaired as a `0xFF` button only after
  the same remote address has already been seen in a complete 24-bit frame.
- Loose pulse timing based on the frame's own median short pulse.

This covers many EV1527/PT2262-like OOK/ASK learning-code remotes. It cannot
guarantee decoding every proprietary or encrypted remote, but it prints raw
pulse data so the protocol can be adjusted after testing.
