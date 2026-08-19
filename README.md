# Gateball Scoreboard Prototypes

This workspace contains the browser-based gateball scoreboard used for Raspberry Pi kiosk deployment:

- `web/`: browser/kiosk version for Raspberry Pi, with scoreboard, phone remote, settings, and local persistence.

## Web Prototype

Run:

```powershell
python web/server.py
```

Open:

- Scoreboard: http://127.0.0.1:8000/scoreboard
- Phone remote: http://127.0.0.1:8000/remote
- Settings: http://127.0.0.1:8000/set

Default controls:

- `1`-`9`: select balls 1-9
- `0`: select ball 10
- `+`: advance selected ball
- `-`: undo selected ball
- `Enter`: start/pause
- `*`: finish match password dialog
- `/`: settings password dialog

Default password is `1234`.

## Raspberry Pi Deployment

For service-mode startup and Chromium kiosk display, see:

```text
deploy/raspberry-pi/README.md
```

The deployment module installs a systemd backend service with automatic restart
and a desktop autostart entry that opens the scoreboard in full-screen kiosk
mode.
