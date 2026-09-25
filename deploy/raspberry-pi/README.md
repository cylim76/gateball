# Raspberry Pi Deployment

This directory installs the web scoreboard as a Raspberry Pi service and opens
the scoreboard in Chromium kiosk mode after desktop login.

## What It Installs

- `gateball.service`: systemd service for `web/server.py`
- `start-kiosk.sh`: disables screen blanking, shows the local startup screen, then opens Chromium on the scoreboard when the service is ready
- `gateball-kiosk.desktop`: desktop autostart entry for the kiosk browser
- `gateball-kiosk-session.sh.template`: optional dedicated kiosk session that avoids loading the normal desktop
- `gateball-x-kiosk.service.template`: optional direct X kiosk service that bypasses the normal desktop entirely
- `splash/splash.html`: local full-screen startup screen shown while the scoreboard starts

The backend service and browser are started separately:

- Backend service keeps scoring, settings, history, and phone remote APIs running.
- Browser only displays `http://127.0.0.1:8000/scoreboard?kiosk=1` on the TV.

This separation is more stable. If the browser crashes, the backend keeps
running. If the backend crashes, systemd restarts it automatically.

After a backend restart or power loss, unfinished scores and the latest timer
checkpoint are restored automatically in a paused state. Press Continue to
resume without entering settings. Downtime is not deducted. Timer checkpoints
are written approximately once per second; score operations are saved before
completion. Finish a cancelled match through the normal password flow before
starting the next one.

## Install

On the Raspberry Pi:

```bash
cd /home/pi/gateball
chmod +x install.sh
./install.sh
```

Run the installer as the desktop user, not with `sudo`. The script asks `sudo`
only for the systemd service install step. This keeps the kiosk autostart entry
under the correct desktop user. If you accidentally run it through `sudo`, the
installer now falls back to `SUDO_USER` so the service and desktop autostart
still target the real Raspberry Pi desktop user.

The installer checks GPIO remote support by trying to import `rpi_rf`. If it is
missing, it installs `python3-pip`, `python3-rpi.gpio`, `python3-lgpio`, and
`rpi-rf` before the service starts. `python3-lgpio` is kept as a fallback for
newer Raspberry Pi boards where `RPi.GPIO` may report
`Cannot determine SOC peripheral base address`. To skip this optional RF
dependency step, run
`INSTALL_RF_SUPPORT=0 ./install.sh`.

The installer does not restart the display manager by default, because that can
close the current desktop terminal before the script finishes. Reboot after
installation. If you deliberately want an immediate display-manager restart, run
`RESTART_DISPLAY_MANAGER=1 ./install.sh`.

If the project is installed somewhere else, run:

```bash
GATEBALL_DIR=/your/gateball/path ./install.sh
```

If your user is not `pi`, the installer uses the current user by default. You
can override it:

```bash
GATEBALL_USER=pi ./install.sh
```

By default, the installer also configures quieter Raspberry Pi boot output. It
backs up the original boot files with a `.gateball.bak` suffix before changing
them, then adds:

- `quiet loglevel=3 vt.global_cursor_default=0 logo.nologo consoleblank=0` to
  the Raspberry Pi kernel command line when available
- `plymouth.enable=0` to the Raspberry Pi kernel command line to disable the
  Raspberry Pi OS graphical boot splash
- `disable_splash=1` to the Raspberry Pi boot config when available

This makes the early boot stage look like a black screen instead of showing
normal boot text, the Raspberry Pi rainbow splash, or the Plymouth startup
screen. When Plymouth services exist, the installer masks them too.

By default, the installer uses the normal Raspberry Pi desktop autostart path.
This is the most reliable mode across Raspberry Pi OS versions: the desktop may
appear briefly, then the kiosk browser opens the local Gateball startup screen
and switches to the scoreboard. Reboot after installation for these changes to
take effect.

To skip the boot-file changes and only install the service/kiosk browser:

```bash
CONFIGURE_QUIET_BOOT=0 ./install.sh
```

There is also an optional dedicated `Gateball Kiosk` LightDM session that tries
to avoid loading the normal desktop. It can reduce desktop flashes, but it is
more sensitive to Raspberry Pi OS session and window-manager differences. Use it
only after the normal autostart mode is working:

```bash
INSTALL_KIOSK_SESSION=1 ./install.sh
```

The default install command is:

```bash
./install.sh
sudo reboot
```

When the board uses one physical Wi-Fi radio for both its normal network and
the Gateball hotspot, the installer checks the currently connected SSID. If
that SSID is advertised on both 2.4 GHz and 5 GHz, the saved connection is
restricted to 2.4 GHz and the hotspot is placed on the matching 2.4 GHz
channel. This prevents NetworkManager from roaming to 5 GHz while the same
radio is serving the hotspot. The installer does not pin a router BSSID, so a
replacement router with the same SSID can still connect. Reboot after a remote
installation so the saved band preference is applied without interrupting the
SSH session.

To keep NetworkManager's original band selection behavior, run:

```bash
GATEBALL_WIFI_PIN_24GHZ=0 ./install.sh
```

There is also an advanced direct X kiosk mode. It backs up and updates
`/etc/X11/Xwrapper.config`, installs `xserver-xorg`, `xinit`, and `openbox`,
disables the normal display manager, boots to `multi-user.target`, and starts
Xorg plus Chromium from systemd:

```bash
INSTALL_DIRECT_X_KIOSK=1 INSTALL_DESKTOP_AUTOSTART=0 ./install.sh
sudo reboot
```

## Kiosk Power Policy

The installer disables Wi-Fi power saving and system suspend, hibernation,
hybrid sleep, and suspend-then-hibernate by default. It adds separate Gateball
configuration files rather than replacing the system's main configuration.
Wi-Fi power saving is also disabled whenever NetworkManager activates or
reapplies a wireless connection, including profiles that explicitly enable it.
This requires `iw`; the network installer normally installs it.

The X11 kiosk launcher already disables screen blanking, screen savers, and
DPMS with `xset`. Desktop lock-screen managers and Wayland compositors may have
their own policies; configure those separately if used. CPU frequency scaling,
thermal protection, and normal shutdown are preserved.

The network installer also installs `gateball-network-sync.timer` and a
NetworkManager dispatcher hook. They read the uplink's actual connected
frequency without requesting a scan, remove a saved router BSSID restriction,
and restart the Gateball hotspot only when its channel no longer matches the
2.4 GHz uplink. This handles routers that automatically change channel after
installation while avoiding periodic hotspot interruptions when the channel is
already correct. If the uplink disconnects, the dispatcher temporarily pauses
the hotspot so the physical radio can reconnect first, then restores the
hotspot. Phones may need to reconnect to the hotspot after this recovery.

For an existing installation, apply only the power policy without restarting
the network, display, or match service:

```bash
sudo bash deploy/raspberry-pi/configure-power.sh install
```

Sleep restrictions and current Wi-Fi power saving are applied immediately;
the logind idle-action setting applies after its next start, normally on reboot.
The system sleep switches require systemd 240 or later (including Ubuntu 20.04
on GB2). To skip this policy on a fresh installation, use
`DISABLE_POWER_SAVING=0 ./install.sh`.

Uninstallation removes the added policy files and restores any pre-existing
files at those same paths. Saved Wi-Fi profiles are not rewritten. To remove
only the policy, run `sudo bash deploy/raspberry-pi/configure-power.sh remove`;
normal Wi-Fi defaults resume on reconnection and idle defaults after reboot.

References: [NetworkManager connection defaults](https://networkmanager.dev/docs/api/latest/NetworkManager.conf.html),
[NetworkManager dispatcher](https://networkmanager.dev/docs/api/latest/NetworkManager-dispatcher.html),
and [systemd sleep policy](https://www.freedesktop.org/software/systemd/man/latest/systemd-sleep.conf.html).

## Useful Commands

```bash
sudo systemctl status gateball
sudo systemctl restart gateball
sudo systemctl stop gateball
journalctl -u gateball -f
```

Open pages:

- Scoreboard: `http://127.0.0.1:8000/scoreboard`
- Kiosk scoreboard: `http://127.0.0.1:8000/scoreboard?kiosk=1`
- Phone remote: `http://<raspberry-pi-ip>:8000/remote`
- Settings: `http://<raspberry-pi-ip>:8000/set`
- Results: `http://<raspberry-pi-ip>:8000/results`

## 433MHz Remote Debug

For standalone RF receiver testing, use `tools/rapsberry-gpio-433test` on the Raspberry
Pi and run it outside the Gateball service. This helps verify the RXB6 wiring
and decoded 24-bit codes without scoreboard state or learning logic involved.

```bash
cd tools/rapsberry-gpio-433test
chmod +x start.sh rf_hex_test.py
./start.sh -decode 27
```

The tool prints decoded values such as:

```text
decoded code=0x57F0FF hex=57 F0 FF address=0x57F0 button=0xFF short_us=417 long_us=1250
```

If no decoded code appears, dump raw pulse timings while pressing a remote
button:

```bash
bash start.sh -dump 27
```

If `rpi-rf` is not installed or cannot start on the current Raspberry Pi, it
falls back to `lgpio` or `RPi.GPIO` and prints pulse frames for protocol
discovery. The main installer installs `rpi-rf` and `python3-lgpio` by default.
On Raspberry Pi OS you can also install the GPIO fallback with:

```bash
sudo apt install -y python3-lgpio
```

The running scoreboard also prefers the `lgpio` GPIO listener when available,
so RF learning in Settings uses the same 24-bit GPIO edge decoder as the Linux
test tool instead of relying only on `rpi-rf`.

The remote settings can run up to four independent 433 MHz receiver sources.
Each source keeps its own GPIO or UART device, and each of the three remotes can
select one or more permitted sources. One ESP32 UART receiver may therefore
serve all remotes, while separate ESP32 devices can be assigned to individual
remotes. Serial paths discovered under `/dev/serial/by-id`, `/dev/ttyUSB*`,
`/dev/ttyACM*`, and `/dev/ttyS*` appear as suggestions; previously saved paths
remain available after switching devices or receiver types. The installer adds
the service user to `dialout` when that group exists.

## Background Music

For production music on Raspberry Pi, put audio files in:

```bash
/home/lucas/gateball-music
```

The app also scans `web/static/audio/music` for test files. Supported formats:
mp3, wav, ogg, and m4a.

Use the printed address code in Settings -> Remote Control to add a remote.

## Kiosk Browser

The kiosk browser starts when the desktop session logs in. It first opens the
local startup screen:

```text
deploy/raspberry-pi/splash/splash.html
```

Startup logs are written to:

```text
/tmp/gateball-kiosk.log
```

The startup script prefers Chromium's real executable paths, such as
`/usr/lib/chromium-browser/chromium-browser` and `/usr/lib/chromium/chromium`,
before falling back to wrapper commands like `chromium`. This avoids older
Raspberry Pi Chromium wrapper flags such as `--no-decommit-pooled-pages` that
newer Chromium builds may reject.

Then it waits for:

```text
http://127.0.0.1:8000/api/state
```

When the backend is ready, it keeps the startup screen visible for at least 10
seconds, then closes it and opens:

```text
http://127.0.0.1:8000/scoreboard?kiosk=1
```

In the optional dedicated kiosk session, closing Chromium exits the kiosk
browser. If LightDM auto-login is still enabled it may start the kiosk session
again. To get back to the normal desktop permanently, run
`deploy/raspberry-pi/uninstall.sh` or reinstall without `INSTALL_KIOSK_SESSION=1`.

To close kiosk manually, press `Alt+F4` or switch terminal and run:

```bash
pkill chromium
pkill chromium-browser
```

The kiosk browser starts Chromium with autoplay enabled and opens the scoreboard
with `kiosk=1`, so the `Enable Sound` button is hidden on the TV. The normal
`/scoreboard` page still shows the button when a desktop or tablet browser
blocks audio during testing.

Chromium is started with a temporary profile under `/tmp/gateball-chromium-profile`.
This keeps the kiosk session disposable, avoids the "restore pages" prompt after
power loss, and reduces desktop keyring prompts on auto-login systems.

The startup screen stays visible for at least 10 seconds and waits up to 180
seconds by default before opening the scoreboard URL. You can change these
values:

```bash
WAIT_SECONDS=240 deploy/raspberry-pi/start-kiosk.sh
MIN_SPLASH_SECONDS=8 deploy/raspberry-pi/start-kiosk.sh
```

## Uninstall

```bash
chmod +x uninstall.sh
./uninstall.sh
```

This removes the systemd service, direct X kiosk service, kiosk autostart entry,
dedicated kiosk session, and LightDM kiosk autologin config. It restores the
system default target to `graphical.target` and re-enables the display manager.
If the installer created `.gateball.bak` boot-file backups, uninstall restores
those files so the Gateball quiet-boot changes are removed. It also unmasks
Plymouth services. It does not remove the project files or match history
database.

Uninstall does not remove kiosk support packages by default. To remove the
packages installed for direct X kiosk mode too:

```bash
REMOVE_KIOSK_PACKAGES=1 ./uninstall.sh
```
