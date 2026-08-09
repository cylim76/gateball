# Gateball Scoreboard Prototypes

This workspace contains two small prototypes for comparing implementation paths:

- `web/`: browser/kiosk version for Raspberry Pi, with scoreboard, phone remote, settings, and local persistence.
- `pyside6/`: native desktop version for keyboard-control comparison.

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

## PySide6 Prototype

Install dependency:

```powershell
python -m pip install -r pyside6/requirements.txt
```

Run:

```powershell
python pyside6/main.py
```

