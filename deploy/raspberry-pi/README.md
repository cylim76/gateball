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

## Install

On the Raspberry Pi:

```bash
cd /home/pi/gateball
chmod +x deploy/raspberry-pi/install.sh
deploy/raspberry-pi/install.sh
```

Run the installer as the desktop user, not with `sudo`. The script asks `sudo`
only for the systemd service install step. This keeps the kiosk autostart entry
under the correct desktop user.

If the project is installed somewhere else, run:

```bash
GATEBALL_DIR=/your/gateball/path deploy/raspberry-pi/install.sh
```

If your user is not `pi`, the installer uses the current user by default. You
can override it:

```bash
GATEBALL_USER=pi deploy/raspberry-pi/install.sh
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

By default, the installer uses the direct X kiosk mode. It installs required
kiosk packages, disables the normal display manager, boots to
`multi-user.target`, and starts Xorg plus Chromium from systemd. This is the
most appliance-like startup mode and avoids loading the normal Raspberry Pi
desktop. Reboot after installation for these changes to take effect.

To skip the boot-file changes and only install the service/kiosk browser:

```bash
CONFIGURE_QUIET_BOOT=0 deploy/raspberry-pi/install.sh
```

There is also an optional dedicated `Gateball Kiosk` LightDM session that tries
to avoid loading the normal desktop. It can reduce desktop flashes, but it is
more sensitive to Raspberry Pi OS session and window-manager differences. Use it
only after the normal autostart mode is working:

```bash
INSTALL_KIOSK_SESSION=1 deploy/raspberry-pi/install.sh
```

The direct X kiosk mode backs up and updates `/etc/X11/Xwrapper.config` so the
kiosk service can start Xorg. It installs `xserver-xorg`, `xinit`, and `openbox`
automatically. The default install command is:

```bash
deploy/raspberry-pi/install.sh
sudo reboot
```

To install the normal desktop autostart mode instead:

```bash
INSTALL_DESKTOP_AUTOSTART=1 deploy/raspberry-pi/install.sh
sudo reboot
```

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

When the backend is ready, it keeps the startup screen visible for at least 5
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

The startup screen stays visible for at least 5 seconds and waits up to 180
seconds by default before opening the scoreboard URL. You can change these
values:

```bash
WAIT_SECONDS=240 deploy/raspberry-pi/start-kiosk.sh
MIN_SPLASH_SECONDS=8 deploy/raspberry-pi/start-kiosk.sh
```

## Uninstall

```bash
chmod +x deploy/raspberry-pi/uninstall.sh
deploy/raspberry-pi/uninstall.sh
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
REMOVE_KIOSK_PACKAGES=1 deploy/raspberry-pi/uninstall.sh
```
