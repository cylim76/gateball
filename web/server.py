from __future__ import annotations

import json
import mimetypes
from threading import RLock
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common.gateball_rules import BallState, new_balls, team_for_ball


HOST = "0.0.0.0"
PORT = 8000
DATA_FILE = ROOT / "data" / "web_state.json"
STATIC_DIR = Path(__file__).resolve().parent / "static"


DEFAULT_STATE = {
    "title": "红星村老年会门球比赛",
    "redTeam": "红队",
    "whiteTeam": "白队",
    "durationSeconds": 30 * 60,
    "remainingSeconds": 30 * 60,
    "running": False,
    "timeExpired": False,
    "selectedBall": 1,
    "finishPassword": "1234",
    "settingsPassword": "1234",
    "allowScoringWhenPaused": False,
    "matchNumber": 1,
    "lastMessage": "等待开始",
    "lastUpdated": None,
    "deadline": None,
    "announcedMinuteWarnings": [],
    "timerStarted": False,
    "lastTickRemainingSeconds": None,
}


class Store:
    def __init__(self) -> None:
        self.lock = RLock()
        self.state = DEFAULT_STATE.copy()
        self.balls = new_balls()
        self.history: list[dict] = []
        self.load()

    def load(self) -> None:
        if not DATA_FILE.exists():
            return
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        self.state.update(data.get("state", {}))
        for key, value in DEFAULT_STATE.items():
            if key not in self.state:
                self.state[key] = value.copy() if isinstance(value, list) else value
        if not isinstance(self.state.get("announcedMinuteWarnings"), list):
            self.state["announcedMinuteWarnings"] = []
        if not isinstance(self.state.get("timerStarted"), bool):
            self.state["timerStarted"] = False
        if self.state.get("running"):
            self.state["timerStarted"] = True
        if self.state.get("lastTickRemainingSeconds") is None:
            self.state["lastTickRemainingSeconds"] = self.state.get("remainingSeconds")
        self.balls = {
            int(number): BallState.from_dict(ball)
            for number, ball in data.get("balls", {}).items()
        }
        for number in range(1, 11):
            self.balls.setdefault(number, BallState(number))
        self.history = data.get("history", [])

    def save(self) -> None:
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "state": self.state,
            "balls": {str(number): ball.to_dict() for number, ball in self.balls.items()},
            "history": self.history[-500:],
        }
        DATA_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def tick(self) -> None:
        if not self.state["running"]:
            return
        deadline = self.state.get("deadline")
        if not deadline:
            return
        previous_remaining = self.state.get("lastTickRemainingSeconds")
        remaining = max(0, int(deadline - time.time()))
        self.state["remainingSeconds"] = remaining
        changed = False
        announced = set(self.state.get("announcedMinuteWarnings", []))
        if remaining > 0:
            for minute in [15, 10, 5, 1]:
                threshold = minute * 60
                crossed_threshold = previous_remaining is not None and previous_remaining > threshold >= remaining
                if crossed_threshold and minute not in announced:
                    announced.add(minute)
                    self.state["announcedMinuteWarnings"] = sorted(announced, reverse=True)
                    self.state["lastMessage"] = f"比赛时间剩余 {minute} 分钟"
                    self.record("timer_warning", None, self.state["lastMessage"])
                    changed = True
                    break
        if remaining == 0 and not self.state.get("timeExpired"):
            self.state["timeExpired"] = True
            self.state["running"] = False
            self.state["lastMessage"] = "时间到"
            self.record("time_expired", None, self.state["lastMessage"])
            changed = True
        self.state["lastTickRemainingSeconds"] = remaining
        if changed:
            self.save()

    def snapshot(self) -> dict:
        with self.lock:
            self.tick()
            balls = [self.balls[number].to_dict() for number in range(1, 11)]
            red_total = sum(ball.score for ball in self.balls.values() if team_for_ball(ball.number) == "red")
            white_total = sum(ball.score for ball in self.balls.values() if team_for_ball(ball.number) == "white")
            return {
                **self.state,
                "balls": balls,
                "redTotal": red_total,
                "whiteTotal": white_total,
                "history": self.history[-30:],
            }

    def record(self, action: str, ball: int | None, message: str) -> None:
        self.history.append(
            {
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "remainingSeconds": int(self.state.get("remainingSeconds", 0)),
                "action": action,
                "ball": ball,
                "message": message,
            }
        )
        self.state["lastUpdated"] = self.history[-1]["time"]

    def reset_match(self) -> str:
        self.balls = new_balls()
        self.state["matchNumber"] += 1
        self.state["remainingSeconds"] = self.state["durationSeconds"]
        self.state["running"] = False
        self.state["timeExpired"] = False
        self.state["deadline"] = None
        self.state["announcedMinuteWarnings"] = []
        self.state["timerStarted"] = False
        self.state["lastTickRemainingSeconds"] = self.state["remainingSeconds"]
        self.state["selectedBall"] = 1
        self.state["lastMessage"] = f"第{self.state['matchNumber']}场，等待开始"
        self.record("next_match", None, self.state["lastMessage"])
        self.save()
        return self.state["lastMessage"]

    def action(self, payload: dict) -> dict:
        self.tick()
        action = payload.get("action")
        message = ""

        if action == "select":
            number = int(payload.get("ball", 1))
            if 1 <= number <= 10:
                self.state["selectedBall"] = number
                message = f"{number}号球"
                self.state["lastMessage"] = message
                self.record("select", number, message)

        elif action == "advance":
            if not self.state["running"] and not self.state["allowScoringWhenPaused"] and not self.state["timeExpired"]:
                message = "暂停期间不能计分"
            else:
                number = int(self.state["selectedBall"])
                message = self.balls[number].advance()
                self.state["lastMessage"] = message
                self.record("advance", number, message)

        elif action == "undo":
            number = int(self.state["selectedBall"])
            message = self.balls[number].undo()
            self.state["lastMessage"] = message
            self.record("undo", number, message)

        elif action == "toggle_timer":
            if self.state["running"]:
                self.tick()
                self.state["running"] = False
                self.state["deadline"] = None
                message = "比赛暂停"
            else:
                if self.state["remainingSeconds"] <= 0:
                    self.state["remainingSeconds"] = self.state["durationSeconds"]
                    self.state["timeExpired"] = False
                    self.state["announcedMinuteWarnings"] = []
                    self.state["timerStarted"] = False
                    self.state["lastTickRemainingSeconds"] = self.state["remainingSeconds"]
                self.state["running"] = True
                self.state["lastTickRemainingSeconds"] = self.state["remainingSeconds"]
                self.state["deadline"] = time.time() + int(self.state["remainingSeconds"])
                message = "比赛开始" if not self.state.get("timerStarted") else "比赛继续"
                self.state["timerStarted"] = True
            self.state["lastMessage"] = message
            self.record("toggle_timer", None, message)

        elif action == "finish":
            if payload.get("password") == self.state["finishPassword"]:
                message = self.reset_match()
            else:
                message = "密码错误"
                self.state["lastMessage"] = message
                self.record("finish_denied", None, message)

        elif action == "update_settings":
            if payload.get("password") != self.state["settingsPassword"]:
                message = "密码错误"
            else:
                for key in ["title", "redTeam", "whiteTeam", "allowScoringWhenPaused"]:
                    if key in payload:
                        self.state[key] = payload[key]
                if "durationMinutes" in payload:
                    minutes = max(1, int(payload["durationMinutes"]))
                    self.state["durationSeconds"] = minutes * 60
                    if not self.state["running"]:
                        self.state["remainingSeconds"] = minutes * 60
                        self.state["announcedMinuteWarnings"] = []
                        self.state["lastTickRemainingSeconds"] = self.state["remainingSeconds"]
                if payload.get("finishPassword"):
                    self.state["finishPassword"] = str(payload["finishPassword"])[:8]
                if payload.get("settingsPassword"):
                    self.state["settingsPassword"] = str(payload["settingsPassword"])[:8]
                message = "设置已保存"
                self.state["lastMessage"] = message
                self.record("settings", None, message)

        else:
            message = "未知操作"

        self.save()
        return {"ok": message != "密码错误", "message": message, "state": self.snapshot()}


store = Store()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in {"/", "/scoreboard"}:
            self.serve_file(STATIC_DIR / "scoreboard.html")
        elif path == "/remote":
            self.serve_file(STATIC_DIR / "remote.html")
        elif path == "/set":
            self.serve_file(STATIC_DIR / "settings.html")
        elif path == "/api/state":
            self.send_json(store.snapshot())
        else:
            target = STATIC_DIR / path.lstrip("/")
            if target.exists() and target.is_file():
                self.serve_file(target)
            else:
                self.send_error(404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/action":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length else "{}"
        payload = json.loads(body)
        with store.lock:
            self.send_json(store.action(payload))

    def serve_file(self, path: Path) -> None:
        content_type = mimetypes.guess_type(path.name)[0] or "text/html"
        if path.suffix.lower() == ".ttf":
            content_type = "font/ttf"
        data = path.read_bytes()
        self.send_response(200)
        if content_type.startswith("text/") or content_type == "application/javascript":
            content_type = f"{content_type}; charset=utf-8"
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Gateball web prototype: http://127.0.0.1:{PORT}/scoreboard")
    print(f"Phone remote: http://127.0.0.1:{PORT}/remote")
    print(f"Settings: http://127.0.0.1:{PORT}/set")
    server.serve_forever()


if __name__ == "__main__":
    main()
