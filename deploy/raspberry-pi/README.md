# Raspberry Pi Deployment

This directory installs the web scoreboard as a Raspberry Pi service and opens
the scoreboard in Chromium kiosk mode after desktop login.

## What It Installs

- `gateball.service`: systemd service for `web/server.py`
- `start-kiosk.sh`: waits for the web service, disables screen blanking, opens Chromium
- `gateball-kiosk.desktop`: desktop autostart entry for the kiosk browser

The backend service and browser are started separately:

- Backend service keeps scoring, settings, history, and phone remote APIs running.
- Browser only displays `http://127.0.0.1:8000/scoreboard` on the TV.

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

## Useful Commands

```bash
sudo systemctl status gateball
sudo systemctl restart gateball
sudo systemctl stop gateball
journalctl -u gateball -f
```

Open pages:

- Scoreboard: `http://127.0.0.1:8000/scoreboard`
- Phone remote: `http://<raspberry-pi-ip>:8000/remote`
- Settings: `http://<raspberry-pi-ip>:8000/set`
- Results: `http://<raspberry-pi-ip>:8000/results`

## Kiosk Browser

The kiosk browser starts when the desktop session logs in. It opens:

```text
http://127.0.0.1:8000/scoreboard
```

To close kiosk manually, press `Alt+F4` or switch terminal and run:

```bash
pkill chromium
pkill chromium-browser
```

The scoreboard page may show an `Enable Sound` button because browsers block
autoplay until a user interacts with the page. Click it once after opening the
scoreboard if sound does not play.

## Uninstall

```bash
chmod +x deploy/raspberry-pi/uninstall.sh
deploy/raspberry-pi/uninstall.sh
```

This removes the systemd service and kiosk autostart entry. It does not remove
the project files or match history database.
