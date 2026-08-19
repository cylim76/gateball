# 433MHz GPIO Test Tool

Copy this folder to the Raspberry Pi, then run:

```bash
cd linux433test
chmod +x start.sh rf_hex_test.py
./start.sh
```

When it asks for a pin, enter the **BCM GPIO number**, not the physical pin
number. For example, BCM GPIO17 is physical pin 11.

The preferred output uses `rpi-rf` and looks like:

```text
code=1234567 hex=12 D6 87 address=123456 button=7 protocol=1 pulse=350
```

If `rpi-rf` is missing, install it:

```bash
sudo apt install -y python3-pip python3-rpi.gpio
sudo python3 -m pip install rpi-rf --break-system-packages
```

If the remote protocol cannot be decoded, the tool may fall back to raw pulse
frames. Raw frames prove that the receiver DATA pin is changing, but they are
not stable decoded button codes.
