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
- `=`: advance selected ball
- `-`: undo selected ball
- `Space`: start/pause/continue
- `Enter`: finish match password dialog
- `Backspace`: ten-second countdown
- `S`: settings password dialog
- `M`: toggle music
- `Esc`: cancel the password dialog

Default settings password is `1234`; default finish password is `9999`.

## Settings and interrupted matches

Opening settings requires the settings password. Once all digits are entered,
verification runs automatically: a correct password opens settings and an
incorrect password closes the prompt. All settings pages share that visit's
temporary session, so saving does not ask for the password again. Closing
settings logs out. Sessions also expire after 12 hours without settings activity
or when the backend restarts. Changing the settings password keeps the current
visit active and invalidates other sessions. Password values are not included
in public state, event streams, or result details.

An unfinished match automatically returns after a power loss or backend restart,
with scores, undo history, and remaining time restored. It remains paused until
the operator presses Continue; this does not require a settings password.
Time while the device is off is not deducted. If a match was cancelled because
of rain, use the normal Finish flow before starting a new match.

Score changes are saved before the action completes. While running, the timer
also saves a small checkpoint approximately once per second, so an abrupt power
loss may restore about one second of extra time (subject to storage delays).
Changing settings after the match starts preserves its remaining time; a new
duration applies to the next match. Network and audio device changes run in the
background, with their status displayed in settings.

## Regression checks

```text
python -B -m unittest discover -s tests -v
node --test tests/test_client.js tests/test_music_client.js
node --check web/static/app.js
```

The checks use temporary databases and simulated clocks/devices. They do not
change live match data, Wi-Fi settings, or audio devices. Node is needed only for
the JavaScript checks; the backend still uses Python's standard library.

Background music remembers the selected file or directory, the current track,
and playback position. Sequence mode continues with the next track in the
selected directory. Random mode saves its shuffled queue so a restart does not
begin the same order again. The scoreboard reports progress about every 25
seconds; a sudden power loss may replay up to roughly that much audio.

## Raspberry Pi Deployment

For service-mode startup and Chromium kiosk display, see:

```text
deploy/raspberry-pi/README.md
```

The deployment module installs a systemd backend service with automatic restart
and a desktop autostart entry that opens the scoreboard in full-screen kiosk
mode.
