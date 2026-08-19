# 433MHz GPIO Test Tool

Copy this folder to the Raspberry Pi, then run:

```bash
cd linux433test
chmod +x start.sh rf_hex_test.py
./start.sh
```

By default, `start.sh` asks for the BCM GPIO number. Press Enter to use GPIO17:

```bash
bash start.sh
```

To use another BCM GPIO without prompts, pass the number directly or after
`-decode`:

```bash
bash start.sh 18
bash start.sh -decode 25
```

`-decode` shows decoded codes only so noise does not scroll the terminal. If
raw pulse timings are needed, use:

```bash
bash start.sh -dump 17
```

When it asks for a pin, enter the **BCM GPIO number**, not the physical pin
number. For example, BCM GPIO17 is physical pin 11. When it asks for a backend,
press Enter to use the default `auto` mode.

You can also run the same test directly:

```bash
python3 rf_hex_test.py --gpio 17 --backend auto
```

If GPIO activity is visible with `gpiomon` but no code is decoded, dump raw
pulse timings while pressing a remote button:

```bash
python3 rf_hex_test.py --gpio 17 --backend lgpio --dump-pulses 120 --gap-us 20000 --min-pulses 8 --show-raw
```

The preferred output uses `rpi-rf` and looks like:

```text
code=1234567 hex=12 D6 87 address=123456 button=7 protocol=1 pulse=350
```

If `rpi-rf` is missing, install it:

```bash
sudo apt install -y python3-pip python3-rpi.gpio python3-lgpio
sudo python3 -m pip install rpi-rf --break-system-packages
```

On newer Raspberry Pi boards or OS builds, `rpi-rf` may fail with
`Cannot determine SOC peripheral base address`. In that case the tool now
continues with `lgpio` automatically and tries to decode the same 24-bit PWM
codes from GPIO edge timings. If `rpi-rf` starts but does not decode your
remote, force the Windows-like GPIO edge decoder with `--backend lgpio`.
The `lgpio` backend tries both normal and inverted signal polarity; inverted
matches are printed as `decoded-inverted`.

If the remote protocol cannot be decoded, the tool may fall back to raw pulse
frames. Raw frames prove that the receiver DATA pin is changing, but they are
not stable decoded button codes.
