from __future__ import annotations

import errno
import json
import mimetypes
import os
import re
import subprocess
from threading import RLock, Thread
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common.gateball_rules import BallState, new_balls, team_for_ball
from common.network_manager import connect_wifi, network_status, scan_wifi_networks
from common.results_store import ResultsStore


HOST = "0.0.0.0"
PORT = 8000
DATA_FILE = ROOT / "data" / "web_state.json"
RESULTS_DB_FILE = ROOT / "data" / "gateball.sqlite3"
STATIC_DIR = Path(__file__).resolve().parent / "static"
TEAM_NAME_AUDIO_DIR = STATIC_DIR / "audio" / "team-names"
WEATHER_CACHE: dict = {"timestamp": 0.0, "payload": {"ok": False}}
SELECTION_TIMEOUT_SECONDS = 30
CLIENT_DISCONNECT_ERRNOS = {
    errno.EPIPE,
    errno.ECONNABORTED,
    errno.ECONNRESET,
    10053,
    10054,
}
VOICE_PROFILES = {"female", "male", "ko-female", "ko-male"}
VOICE_PROFILE_DIRS = {
    "female": "voice-cn-female",
    "male": "voice-cn-male",
    "ko-female": "voice-ko-female",
    "ko-male": "voice-ko-male",
}


DEFAULT_STATE = {
    "title": "红星村老年会门球比赛",
    "redTeam": "红队",
    "whiteTeam": "白队",
    "durationSeconds": 30 * 60,
    "remainingSeconds": 30 * 60,
    "running": False,
    "timeExpired": False,
    "matchFinished": False,
    "selectedBall": 1,
    "selectedBallAt": None,
    "finishPassword": "0000",
    "settingsPassword": "1234",
    "allowScoringWhenPaused": False,
    "matchNumber": 1,
    "lastMessage": "等待开始",
    "lastUpdated": None,
    "deadline": None,
    "announcedMinuteWarnings": [],
    "timerStarted": False,
    "matchStartedAt": None,
    "lastTickRemainingSeconds": None,
    "tenSecondCountdownId": None,
    "tenSecondCountdownStartedAt": None,
    "keyBindings": {},
    "voiceProfile": "female",
    "voicePlaybackRate": 1.2,
    "weatherLocation": "西安区, 牡丹江市, 黑龙江省, 157000, 中国",
    "weatherLatitude": 44.488144,
    "weatherLongitude": 129.5093059,
    "courtName": "红星门球场1",
    "hotspotSsid": "红星门球场1",
    "hotspotPassword": "12345678",
}


def atomic_write_json(path: Path, payload: dict) -> None:
    temp_path = path.with_name(f"{path.name}.tmp")
    data = json.dumps(payload, ensure_ascii=False, indent=2)
    with temp_path.open("w", encoding="utf-8") as handle:
        handle.write(data)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temp_path.replace(path)


def is_client_disconnect(error: OSError) -> bool:
    return getattr(error, "errno", None) in CLIENT_DISCONNECT_ERRNOS or getattr(error, "winerror", None) in CLIENT_DISCONNECT_ERRNOS


def normalize_team_name(name: str) -> str:
    return re.sub(r"\s+", " ", str(name or "").strip())[:40]


def is_default_team_name(team: str, name: str) -> bool:
    normalized = normalize_team_name(name)
    defaults = {"red": {"红队", "홍팀", "Red Team"}, "white": {"白队", "백팀", "White Team"}}
    return not normalized or normalized in defaults.get(team, set())


def team_name_voice_profile(profile: str, name: str) -> str:
    profile = profile if profile in VOICE_PROFILES else "female"
    is_male = profile in {"male", "ko-male"}
    text = str(name or "")
    if re.search(r"[\uac00-\ud7af]", text):
        return "ko-male" if is_male else "ko-female"
    if re.search(r"[\u3400-\u9fff]", text):
        return "male" if is_male else "female"
    return profile


def generate_team_name_audio(profile: str, team: str, name: str) -> dict:
    team = team if team in {"red", "white"} else "team"
    name = normalize_team_name(name)
    profile = team_name_voice_profile(profile, name)
    if not name:
        return {"ok": False, "message": "队名为空"}
    script = ROOT / "tools" / "generate_voice_assets.py"
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        result = subprocess.run(
            [sys.executable, str(script), "team-name", profile, team, name],
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            env=env,
            timeout=60,
        )
    except Exception as exc:
        return {"ok": False, "message": str(exc)}
    if result.returncode != 0:
        return {"ok": False, "message": result.stderr.strip() or result.stdout.strip() or "队名语音生成失败"}
    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        return {"ok": False, "message": "队名语音生成结果无效"}
    return {"ok": True, **payload}


def warm_team_name_audio_cache(team: str, name: str) -> None:
    if is_default_team_name(team, name):
        return

    def worker() -> None:
        for profile in {team_name_voice_profile(profile, name) for profile in VOICE_PROFILES}:
            generate_team_name_audio(profile, team, name)

    Thread(target=worker, daemon=True).start()


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
        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.quarantine_broken_state_file()
            return
        self.state.update(data.get("state", {}))
        for key, value in DEFAULT_STATE.items():
            if key not in self.state:
                self.state[key] = value.copy() if isinstance(value, list) else value
        if not isinstance(self.state.get("announcedMinuteWarnings"), list):
            self.state["announcedMinuteWarnings"] = []
        if not isinstance(self.state.get("timerStarted"), bool):
            self.state["timerStarted"] = False
        if not isinstance(self.state.get("matchFinished"), bool):
            self.state["matchFinished"] = False
        if "matchStartedAt" not in self.state:
            self.state["matchStartedAt"] = None
        if not isinstance(self.state.get("keyBindings"), dict):
            self.state["keyBindings"] = {}
        if "selectedBallAt" not in self.state:
            self.state["selectedBallAt"] = None
        if self.state.get("finishPassword") == "1234":
            self.state["finishPassword"] = "0000"
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
        atomic_write_json(DATA_FILE, payload)

    def quarantine_broken_state_file(self) -> None:
        if not DATA_FILE.exists():
            return
        stamp = time.strftime("%Y%m%d_%H%M%S")
        target = DATA_FILE.with_name(f"{DATA_FILE.stem}_broken_{stamp}{DATA_FILE.suffix}")
        try:
            DATA_FILE.replace(target)
        except OSError:
            pass

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
                "serverTime": time.time(),
                "history": self.history[-30:],
            }

    def record(self, action: str, ball: int | None, message: str) -> None:
        self.history.append(
            {
                "id": f"{time.time():.6f}",
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
        self.state["matchFinished"] = False
        self.state["deadline"] = None
        self.state["announcedMinuteWarnings"] = []
        self.state["timerStarted"] = False
        self.state["matchStartedAt"] = None
        self.state["lastTickRemainingSeconds"] = self.state["remainingSeconds"]
        self.state["selectedBall"] = 1
        self.state["selectedBallAt"] = None
        self.state["lastMessage"] = f"第{self.state['matchNumber']}场，等待开始"
        self.record("next_match", None, self.state["lastMessage"])
        self.save()
        return self.state["lastMessage"]

    def has_fresh_selected_ball(self) -> bool:
        selected_at = self.state.get("selectedBallAt")
        if selected_at is None:
            return False
        try:
            age = time.time() - float(selected_at)
        except (TypeError, ValueError):
            return False
        return age <= SELECTION_TIMEOUT_SECONDS

    def require_selected_ball(self) -> bool:
        if self.has_fresh_selected_ball():
            return True
        message = "请先选择球号"
        self.state["lastMessage"] = message
        self.record("selection_required", None, message)
        return False

    def action(self, payload: dict) -> dict:
        self.tick()
        action = payload.get("action")
        message = ""

        if action == "select":
            number = int(payload.get("ball", 1))
            if 1 <= number <= 10:
                self.state["selectedBall"] = number
                self.state["selectedBallAt"] = time.time()
                message = f"{number}号球"
                self.state["lastMessage"] = message
                self.record("select", number, message)

        elif action == "advance":
            if self.state.get("matchFinished"):
                message = self.state.get("lastMessage", "")
            elif not self.require_selected_ball():
                message = self.state["lastMessage"]
            elif not self.state["running"] and not self.state["allowScoringWhenPaused"] and not self.state["timeExpired"]:
                message = "暂停期间不能计分"
            else:
                number = int(self.state["selectedBall"])
                message = self.balls[number].advance()
                self.state["lastMessage"] = message
                self.record("advance", number, message)

        elif action == "undo":
            if self.state.get("matchFinished"):
                message = self.state.get("lastMessage", "")
            elif not self.require_selected_ball():
                message = self.state["lastMessage"]
            else:
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
                if not self.state.get("timerStarted"):
                    self.state["matchStartedAt"] = time.strftime("%Y-%m-%d %H:%M:%S")
                self.state["timerStarted"] = True
            self.state["lastMessage"] = message
            self.record("toggle_timer", None, message)

        elif action == "ten_second_countdown":
            message = "10秒倒计时"
            event_id = f"{time.time():.6f}"
            self.state["tenSecondCountdownId"] = event_id
            self.state["tenSecondCountdownStartedAt"] = time.time()
            self.state["lastMessage"] = message
            self.record("ten_second_countdown", None, message)

        elif action == "cancel_ten_second_countdown":
            message = "10秒倒计时已停止"
            self.state["tenSecondCountdownId"] = None
            self.state["tenSecondCountdownStartedAt"] = None
            self.state["lastMessage"] = message
            self.record("cancel_ten_second_countdown", None, message)

        elif action == "swap_team_names":
            red_team = str(self.state.get("redTeam", "")).strip()
            white_team = str(self.state.get("whiteTeam", "")).strip()
            if red_team or white_team:
                self.state["redTeam"], self.state["whiteTeam"] = self.state["whiteTeam"], self.state["redTeam"]
                message = "红白队名已更换"
            else:
                message = "队名为空"
            self.state["lastMessage"] = message
            self.record("swap_team_names", None, message)

        elif action == "set_team_name":
            team = payload.get("team")
            name = str(payload.get("name", ""))[:40]
            if team == "red":
                self.state["redTeam"] = name
                message = "红队队名已保存"
                warm_team_name_audio_cache("red", name)
            elif team == "white":
                self.state["whiteTeam"] = name
                message = "白队队名已保存"
                warm_team_name_audio_cache("white", name)
            else:
                message = "未知队伍"
            self.state["lastMessage"] = message
            self.record("set_team_name", None, message)

        elif action == "set_title":
            title = str(payload.get("title", "")).strip()[:40]
            self.state["title"] = title or DEFAULT_STATE["title"]
            message = "比赛标题已保存"
            self.state["lastMessage"] = message
            self.record("set_title", None, message)

        elif action == "finish":
            if payload.get("password") == self.state["finishPassword"]:
                finished_snapshot = self.snapshot()
                if not self.state.get("matchFinished"):
                    results_store.save_match(finished_snapshot)
                    self.state["running"] = False
                    self.state["deadline"] = None
                    self.state["matchFinished"] = True
                    message = "match finished"
                    self.state["lastMessage"] = message
                    self.record("finish", None, message)
                    self.save()
                else:
                    message = self.state.get("lastMessage") or "match finished"
                return {"ok": True, "message": message, "finishedMatch": finished_snapshot, "state": self.snapshot()}
            else:
                message = "密码错误"
                self.state["lastMessage"] = message
                self.record("finish_denied", None, message)

        elif action == "advance_to_next_match":
            if self.state.get("matchFinished"):
                message = self.reset_match()
                return {"ok": True, "message": message, "state": self.snapshot()}
            message = self.state.get("lastMessage", "")

        elif action == "update_settings":
            if payload.get("password") != self.state["settingsPassword"]:
                message = "密码错误"
            else:
                for key in ["allowScoringWhenPaused", "weatherLocation", "courtName", "hotspotSsid"]:
                    if key in payload:
                        self.state[key] = str(payload[key]).strip() if key != "allowScoringWhenPaused" else payload[key]
                        if key == "weatherLocation":
                            WEATHER_CACHE["timestamp"] = 0.0
                if "courtName" in payload and "hotspotSsid" not in payload:
                    self.state["hotspotSsid"] = str(payload["courtName"]).strip()
                if "hotspotPassword" in payload:
                    password = str(payload["hotspotPassword"]).strip()
                    if len(password) >= 8:
                        self.state["hotspotPassword"] = password[:63]
                if "weatherLatitude" in payload and "weatherLongitude" in payload:
                    try:
                        self.state["weatherLatitude"] = float(payload["weatherLatitude"]) if str(payload["weatherLatitude"]).strip() else None
                        self.state["weatherLongitude"] = float(payload["weatherLongitude"]) if str(payload["weatherLongitude"]).strip() else None
                        WEATHER_CACHE["timestamp"] = 0.0
                    except ValueError:
                        self.state["weatherLatitude"] = None
                        self.state["weatherLongitude"] = None
                if payload.get("voiceProfile") in VOICE_PROFILES:
                    self.state["voiceProfile"] = payload["voiceProfile"]
                if "voicePlaybackRate" in payload:
                    try:
                        rate = round(float(payload["voicePlaybackRate"]), 1)
                        self.state["voicePlaybackRate"] = min(2.0, max(0.8, rate))
                    except (TypeError, ValueError):
                        pass
                if "durationMinutes" in payload:
                    minutes = max(1, int(payload["durationMinutes"]))
                    self.state["durationSeconds"] = minutes * 60
                    if not self.state["running"]:
                        self.state["remainingSeconds"] = minutes * 60
                        self.state["announcedMinuteWarnings"] = []
                        self.state["lastTickRemainingSeconds"] = self.state["remainingSeconds"]
                if payload.get("finishPassword"):
                    password = "".join(ch for ch in str(payload["finishPassword"]) if ch.isdigit())[:6]
                    if password:
                        self.state["finishPassword"] = password
                if payload.get("settingsPassword"):
                    password = "".join(ch for ch in str(payload["settingsPassword"]) if ch.isdigit())[:6]
                    if password:
                        self.state["settingsPassword"] = password
                message = "设置已保存"
                self.state["lastMessage"] = message
                self.record("settings", None, message)

        elif action == "update_key_binding":
            binding_action = str(payload.get("bindingAction", "")).strip()
            code = str(payload.get("code", "")).strip()
            key = str(payload.get("key", "")).strip()
            label = str(payload.get("label", "")).strip()
            if binding_action and (code or key):
                bindings = self.state.setdefault("keyBindings", {})
                bindings[binding_action] = {
                    "code": code,
                    "key": key,
                    "label": label or code or key,
                }
                message = "按键映射已保存"
                self.state["lastMessage"] = message
                self.record("key_binding", None, message)
            else:
                message = "按键映射失败"

        else:
            message = "未知操作"

        self.save()
        return {"ok": message != "密码错误", "message": message, "state": self.snapshot()}


results_store = ResultsStore(RESULTS_DB_FILE)
store = Store()


def weather_icon(code: int) -> str:
    if code == 113:
        return "☀"
    if code in {116, 119, 122, 143, 248, 260}:
        return "☁"
    if code in {176, 263, 266, 281, 284, 293, 296, 299, 302, 305, 308, 353, 356, 359}:
        return "☂"
    if code in {179, 182, 185, 227, 230, 311, 314, 317, 320, 323, 326, 329, 332, 335, 338, 362, 365, 368, 371, 374, 377}:
        return "❄"
    if code in {200, 386, 389, 392, 395}:
        return "⚡"
    return "☁"


def open_meteo_weather_icon(code: int) -> str:
    if code == 0:
        return "☀"
    if code in {1, 2, 3, 45, 48}:
        return "☁"
    if code in {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}:
        return "☂"
    if code in {71, 73, 75, 77, 85, 86}:
        return "❄"
    if code in {95, 96, 99}:
        return "⚡"
    return "☁"


def fetch_weather() -> dict:
    now = time.time()
    if now - float(WEATHER_CACHE.get("timestamp", 0)) < 1800:
        return WEATHER_CACHE["payload"]

    try:
        latitude = store.state.get("weatherLatitude")
        longitude = store.state.get("weatherLongitude")
        if latitude is not None and longitude is not None:
            url = (
                "https://api.open-meteo.com/v1/forecast"
                f"?latitude={float(latitude):.5f}&longitude={float(longitude):.5f}"
                "&daily=weather_code,temperature_2m_max,temperature_2m_min"
                "&timezone=auto&forecast_days=1"
            )
            with urlopen(url, timeout=4) as response:
                data = json.loads(response.read().decode("utf-8"))
            daily = data["daily"]
            code = int(daily["weather_code"][0])
            payload = {
                "ok": True,
                "icon": open_meteo_weather_icon(code),
                "minTempC": int(round(float(daily["temperature_2m_min"][0]))),
                "maxTempC": int(round(float(daily["temperature_2m_max"][0]))),
            }
        else:
            with urlopen("https://wttr.in/auto:ip?format=j1&lang=zh", timeout=4) as response:
                data = json.loads(response.read().decode("utf-8"))
            today = data["weather"][0]
            current = data["current_condition"][0]
            code = int(current.get("weatherCode", 0))
            payload = {
                "ok": True,
                "icon": weather_icon(code),
                "minTempC": int(float(today["mintempC"])),
                "maxTempC": int(float(today["maxtempC"])),
            }
    except Exception:
        payload = {"ok": False}

    WEATHER_CACHE["timestamp"] = now
    WEATHER_CACHE["payload"] = payload
    return payload


def search_weather_locations(query: str) -> dict:
    query = query.strip()
    if not query:
        return {"ok": True, "results": []}
    try:
        url = (
            "https://geocoding-api.open-meteo.com/v1/search"
            f"?name={quote(query)}&count=8&language=zh&format=json"
        )
        with urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
        results = []
        for item in data.get("results", []):
            parts = [
                item.get("name"),
                item.get("admin3"),
                item.get("admin2"),
                item.get("admin1"),
                item.get("country"),
            ]
            label = " / ".join(dict.fromkeys(str(part) for part in parts if part))
            results.append(
                {
                    "name": label,
                    "latitude": item.get("latitude"),
                    "longitude": item.get("longitude"),
                }
            )
        if results:
            return {"ok": True, "results": results}
        return search_backup_weather_locations(query)
    except Exception:
        return search_backup_weather_locations(query)


def search_backup_weather_locations(query: str) -> dict:
    try:
        url = (
            "https://nominatim.openstreetmap.org/search"
            f"?q={quote(query)}&format=json&limit=8&accept-language=zh-CN"
        )
        request = Request(url, headers={"User-Agent": "gateball-scoreboard/1.0"})
        with urlopen(request, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
        results = []
        for item in data:
            label = item.get("display_name") or item.get("name")
            if not label:
                continue
            results.append(
                {
                    "name": label,
                    "latitude": item.get("lat"),
                    "longitude": item.get("lon"),
                }
            )
        return {"ok": True, "results": results}
    except Exception:
        return {"ok": False, "results": []}


class Handler(BaseHTTPRequestHandler):
    def handle(self) -> None:
        try:
            super().handle()
        except OSError as exc:
            if is_client_disconnect(exc):
                return
            raise

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self.serve_file(STATIC_DIR / "remote.html")
        elif path == "/scoreboard":
            self.serve_file(STATIC_DIR / "scoreboard.html")
        elif path == "/remote":
            self.serve_file(STATIC_DIR / "remote.html")
        elif path == "/results":
            self.serve_file(STATIC_DIR / "results.html")
        elif path == "/set":
            self.serve_file(STATIC_DIR / "settings.html")
        elif path == "/api/events":
            self.send_events()
        elif path == "/api/state":
            self.send_json(store.snapshot())
        elif path == "/api/network/status":
            self.send_json(network_status(store.state))
        elif path == "/api/network/scan":
            self.send_json(scan_wifi_networks())
        elif path == "/api/results/month":
            params = parse_qs(urlparse(self.path).query)
            now = time.localtime()
            year = int(params.get("year", [now.tm_year])[0])
            month = int(params.get("month", [now.tm_mon])[0])
            self.send_json(results_store.month_summary(year, month))
        elif path == "/api/results/day":
            params = parse_qs(urlparse(self.path).query)
            self.send_json(results_store.matches_for_day(params.get("date", [""])[0]))
        elif path == "/api/results/match":
            params = parse_qs(urlparse(self.path).query)
            self.send_json(results_store.match_detail(int(params.get("id", ["0"])[0])))
        elif path == "/api/weather":
            self.send_json(fetch_weather())
        elif path == "/api/weather/search":
            params = parse_qs(urlparse(self.path).query)
            self.send_json(search_weather_locations(params.get("q", [""])[0]))
        else:
            target = STATIC_DIR / path.lstrip("/")
            if target.exists() and target.is_file():
                self.serve_file(target)
            else:
                self.send_error(404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in {"/api/action", "/api/network/connect", "/api/voice/team-name"}:
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length else "{}"
        payload = json.loads(body)
        if path == "/api/network/connect":
            self.send_json(connect_wifi(str(payload.get("ssid", "")), str(payload.get("password", ""))))
            return
        if path == "/api/voice/team-name":
            self.send_json(
                generate_team_name_audio(
                    str(payload.get("profile", "")),
                    str(payload.get("team", "")),
                    str(payload.get("name", "")),
                )
            )
            return
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
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def send_json(self, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(data)
        except OSError as exc:
            if is_client_disconnect(exc):
                return
            raise

    def send_events(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        last_key: tuple | None = None
        last_heartbeat = time.time()
        while True:
            with store.lock:
                snapshot = store.snapshot()
            event_key = (
                snapshot.get("lastUpdated"),
                snapshot.get("remainingSeconds"),
                snapshot.get("running"),
                snapshot.get("timeExpired"),
                snapshot.get("selectedBall"),
                snapshot.get("selectedBallAt"),
                snapshot.get("redTotal"),
                snapshot.get("whiteTotal"),
                snapshot.get("tenSecondCountdownId"),
            )
            now = time.time()
            should_send = event_key != last_key
            should_heartbeat = now - last_heartbeat >= 15
            if should_send:
                data = json.dumps(snapshot, ensure_ascii=False)
                try:
                    self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    return
                last_key = event_key
                last_heartbeat = now
            elif should_heartbeat:
                try:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    return
                last_heartbeat = now
            time.sleep(0.2)

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
