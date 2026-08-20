from __future__ import annotations

import errno
import json
import mimetypes
import os
import re
import select
import shutil
import subprocess
from dataclasses import dataclass
from queue import SimpleQueue
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
from common.network_manager import (
    DEFAULT_HOTSPOT_PASSWORD,
    DEFAULT_HOTSPOT_SSID,
    configure_hotspot,
    connect_wifi,
    network_status,
    scan_wifi_networks,
)
from common.results_store import ResultsStore


HOST = "0.0.0.0"
PORT = 8000
DATA_FILE = ROOT / "data" / "web_state.json"
RESULTS_DB_FILE = ROOT / "data" / "gateball.sqlite3"
STATIC_DIR = Path(__file__).resolve().parent / "static"
TEAM_NAME_AUDIO_DIR = STATIC_DIR / "audio" / "team-names"
PROJECT_MUSIC_DIR = STATIC_DIR / "audio" / "music"
EXTERNAL_MUSIC_DIRS = [
    Path("/home/lucas/gateball-music"),
    Path.home() / "gateball-music",
    Path("/home/lucas/Music"),
    Path("/home/lucas/音乐"),
    Path.home() / "Music",
    Path.home() / "音乐",
]
MUSIC_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a"}
MUSIC_TRACKS_CACHE: dict[str, object] = {"timestamp": 0.0, "tracks": []}
MUSIC_TRACKS_CACHE_TTL = 15.0
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
RF_REMOTE_MODELS = {
    "gateball-10key": {
        "name": "10-key gateball remote",
        "buttons": {
            "1": "ball_1",
            "2": "ball_2",
            "3": "ball_3",
            "4": "ball_4",
            "5": "ball_5",
            "6": "ball_6",
            "7": "ball_7",
            "8": "ball_8",
            "9": "ball_9",
            "10": "ball_10",
            "0": "ball_10",
            "+": "advance",
            "-": "undo",
            "OK": "toggle_timer",
            "#": "ten_second_countdown",
            "M": "toggle_music",
            "*": "finish_dialog",
        },
    }
}
RF_ACTION_PAYLOADS = {
    "ball_1": {"action": "select", "ball": 1},
    "ball_2": {"action": "select", "ball": 2},
    "ball_3": {"action": "select", "ball": 3},
    "ball_4": {"action": "select", "ball": 4},
    "ball_5": {"action": "select", "ball": 5},
    "ball_6": {"action": "select", "ball": 6},
    "ball_7": {"action": "select", "ball": 7},
    "ball_8": {"action": "select", "ball": 8},
    "ball_9": {"action": "select", "ball": 9},
    "ball_10": {"action": "select", "ball": 10},
    "advance": {"action": "advance"},
    "undo": {"action": "undo"},
    "toggle_timer": {"action": "toggle_timer"},
    "swap_team_names": {"action": "swap_team_names"},
    "ten_second_countdown": {"action": "ten_second_countdown"},
    "toggle_music": {"action": "toggle_music"},
}
RF_ACTION_IDS = set(RF_ACTION_PAYLOADS) | {"finish_dialog"}
DEFAULT_RF_REMOTE_SLOTS = [
    {"id": "rf1", "name": "遥控器1", "enabled": False, "bindings": {}},
    {"id": "rf2", "name": "遥控器2", "enabled": False, "bindings": {}},
    {"id": "rf3", "name": "遥控器3", "enabled": False, "bindings": {}},
]


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
    "finishPassword": "9999",
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
    "systemVolumePercent": 100,
    "musicEnabled": False,
    "musicVolumePercent": 35,
    "musicMode": "random",
    "musicAutoPlayDuringMatch": True,
    "musicStopWhenMatchEnds": False,
    "musicDuckDuringSpeech": True,
    "musicDuckPercent": 30,
    "selectedMusicTrack": "",
    "musicPlaying": False,
    "musicDuckingUntil": 0,
    "lastMusicToggleAt": 0,
    "titleColor": "#ffe23a",
    "titleFontScale": 1.0,
    "teamNameAutoSize": True,
    "teamNameScale": 1.0,
    "tableMarkerAutoSize": True,
    "tableMarkerScale": 1.0,
    "weatherLocation": "西安区, 牡丹江市, 黑龙江省, 157000, 中国",
    "weatherLatitude": 44.488144,
    "weatherLongitude": 129.5093059,
    "courtName": "红星门球场1",
    "hotspotSsid": DEFAULT_HOTSPOT_SSID,
    "hotspotPassword": DEFAULT_HOTSPOT_PASSWORD,
    "showBootWifiInfo": True,
}


def set_system_volume_percent(percent: int) -> bool:
    percent = min(100, max(0, int(percent)))
    commands = [
        ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{percent / 100:.2f}"],
        ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{percent}%"],
        ["amixer", "sset", "Master", f"{percent}%"],
        ["amixer", "-D", "pulse", "sset", "Master", f"{percent}%"],
        ["amixer", "-D", "default", "sset", "PCM", f"{percent}%"],
    ]
    for command in commands:
        try:
            result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0:
            if command[0] == "wpctl":
                try:
                    subprocess.run(
                        ["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "1" if percent == 0 else "0"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=2,
                    )
                except (OSError, subprocess.SubprocessError):
                    pass
            elif command[0] == "pactl":
                try:
                    subprocess.run(
                        ["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1" if percent == 0 else "0"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=2,
                    )
                except (OSError, subprocess.SubprocessError):
                    pass
            return True
    return False


def music_directories() -> list[tuple[str, Path]]:
    directories = [("external", path) for path in EXTERNAL_MUSIC_DIRS]
    directories.append(("project", PROJECT_MUSIC_DIR))
    unique = []
    seen = set()
    source_counts: dict[str, int] = {}
    for source, path in directories:
        resolved = path.expanduser()
        try:
            key = str(resolved.resolve())
        except OSError:
            key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        source_counts[source] = source_counts.get(source, 0) + 1
        source_id = source if source_counts[source] == 1 else f"{source}-{source_counts[source]}"
        unique.append((source_id, resolved))
    return unique


def music_track_id(source: str, relative_path: Path) -> str:
    return f"{source}:{relative_path.as_posix()}"


def music_directory_id(source: str, relative_path: Path) -> str:
    return f"dir:{source}:{relative_path.as_posix()}"


def music_source_label(source: str) -> str:
    return "external" if source.startswith("external") else "project"


def list_music_items() -> tuple[list[dict], list[dict]]:
    items = []
    tracks = []
    for source, directory in music_directories():
        if not directory.exists() or not directory.is_dir():
            continue
        items.append(
            {
                "id": music_directory_id(source, Path(".")),
                "type": "directory",
                "name": directory.name or directory.as_posix(),
                "source": music_source_label(source),
                "deletable": False,
            }
        )
        for path in sorted(directory.rglob("*")):
            if not path.is_dir():
                continue
            try:
                relative = path.relative_to(directory)
            except ValueError:
                continue
            if not relative.parts:
                continue
            item_id = music_directory_id(source, relative)
            items.append(
                {
                    "id": item_id,
                    "type": "directory",
                    "name": relative.as_posix(),
                    "source": music_source_label(source),
                    "deletable": True,
                }
            )
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in MUSIC_EXTENSIONS:
                continue
            try:
                relative = path.relative_to(directory)
            except ValueError:
                continue
            track_id = music_track_id(source, relative)
            track = {
                "id": track_id,
                "type": "track",
                "name": relative.as_posix(),
                "displayName": path.stem,
                "fileName": path.name,
                "source": music_source_label(source),
                "deletable": True,
                "url": f"/api/music/file?id={quote(track_id)}",
            }
            tracks.append(track)
            items.append(track)
    return tracks, items


def list_music_tracks() -> list[dict]:
    cached_at = float(MUSIC_TRACKS_CACHE.get("timestamp") or 0)
    cached_tracks = MUSIC_TRACKS_CACHE.get("tracks")
    if isinstance(cached_tracks, list) and cached_tracks and time.time() - cached_at < MUSIC_TRACKS_CACHE_TTL:
        return [dict(track) for track in cached_tracks if isinstance(track, dict)]
    tracks, _items = list_music_items()
    MUSIC_TRACKS_CACHE["timestamp"] = time.time()
    MUSIC_TRACKS_CACHE["tracks"] = tracks
    return tracks


def next_music_track_id(current_track_id: str, mode: str = "loop") -> str:
    tracks = list_music_tracks()
    if not tracks:
        return ""
    if len(tracks) == 1:
        return str(tracks[0].get("id") or "")
    if mode == "random":
        choices = [str(track.get("id") or "") for track in tracks if track.get("id") != current_track_id]
        return random.choice(choices) if choices else str(tracks[0].get("id") or "")
    current_index = next(
        (index for index, track in enumerate(tracks) if track.get("id") == current_track_id),
        -1,
    )
    return str(tracks[(current_index + 1) % len(tracks)].get("id") or "")


def resolve_music_track(track_id: str) -> Path | None:
    if ":" not in track_id:
        return None
    source, relative_text = track_id.split(":", 1)
    if not relative_text:
        return None
    relative = Path(relative_text)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    for candidate_source, directory in music_directories():
        if candidate_source != source:
            continue
        base = directory.resolve()
        target = (base / relative).resolve()
        try:
            target.relative_to(base)
        except ValueError:
            return None
        if target.exists() and target.is_file() and target.suffix.lower() in MUSIC_EXTENSIONS:
            return target
    return None


def resolve_music_item(item_id: str) -> tuple[str, Path] | None:
    if item_id.startswith("dir:"):
        rest = item_id[4:]
        if ":" not in rest:
            return None
        source, relative_text = rest.split(":", 1)
        if not relative_text:
            return None
        relative = Path(relative_text)
        if relative.is_absolute() or ".." in relative.parts:
            return None
        for candidate_source, directory in music_directories():
            if candidate_source != source:
                continue
            base = directory.resolve()
            target = (base / relative).resolve()
            try:
                target.relative_to(base)
            except ValueError:
                return None
            if target == base:
                return None
            if target.exists() and target.is_dir():
                return ("directory", target)
        return None
    target = resolve_music_track(item_id)
    if target:
        return ("track", target)
    return None


def default_rf_remote_slots() -> list[dict]:
    return [
        {
            "id": slot["id"],
            "name": slot["name"],
            "enabled": parse_bool(slot.get("enabled")),
            "bindings": {},
        }
        for slot in DEFAULT_RF_REMOTE_SLOTS
    ]


def parse_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on", "enabled"}:
            return True
        if text in {"0", "false", "no", "off", "disabled", ""}:
            return False
    return default


DEFAULT_STATE.update(
    {
        "rfRemoteEnabled": True,
        "rfReceiverType": "gpio",
        "rfReceiverGpio": 27,
        "rfReceiverSerialDevice": "",
        "rfRemoteModel": "gateball-10key",
        "rfRemotes": [],
        "rfRemoteSlots": default_rf_remote_slots(),
        "rfLastSignal": None,
        "rfFinishPasswordPending": False,
        "rfLearning": None,
        "keyboardInputEnabled": True,
    }
)


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
        self.preview_state: dict = {}
        self.balls = new_balls()
        self.history: list[dict] = []
        self.last_rf_music_raw = ""
        self.last_rf_music_at = 0.0
        self.load()
        self.apply_boot_music_autoplay()
        self.record_boot_wifi_info()

    def apply_boot_music_autoplay(self) -> None:
        if self.state.get("musicEnabled") and self.state.get("musicAutoPlayDuringMatch") and self.state.get("selectedMusicTrack"):
            self.state["musicPlaying"] = True

    def record_boot_wifi_info(self) -> None:
        if not self.state.get("showBootWifiInfo", True):
            return
        ssid = str(self.state.get("hotspotSsid") or DEFAULT_HOTSPOT_SSID).strip() or DEFAULT_HOTSPOT_SSID
        password = str(self.state.get("hotspotPassword") or DEFAULT_HOTSPOT_PASSWORD).strip() or DEFAULT_HOTSPOT_PASSWORD
        self.record("boot_wifi_info", None, f"WiFi：{ssid} / {password}    http://gateball")
        self.state["lastMessage"] = self.history[-1]["message"]
        self.save()

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
        if not isinstance(self.state.get("keyboardInputEnabled"), bool):
            self.state["keyboardInputEnabled"] = True
        if not str(self.state.get("hotspotSsid") or "").strip():
            self.state["hotspotSsid"] = DEFAULT_HOTSPOT_SSID
        if not str(self.state.get("hotspotPassword") or "").strip():
            self.state["hotspotPassword"] = DEFAULT_HOTSPOT_PASSWORD
        if (
            str(self.state.get("hotspotPassword") or "") == "12345678"
            and str(self.state.get("hotspotSsid") or "").strip() == str(self.state.get("courtName") or "").strip()
        ):
            self.state["hotspotSsid"] = DEFAULT_HOTSPOT_SSID
            self.state["hotspotPassword"] = DEFAULT_HOTSPOT_PASSWORD
        if not isinstance(self.state.get("showBootWifiInfo"), bool):
            self.state["showBootWifiInfo"] = parse_bool(self.state.get("showBootWifiInfo"), True)
        try:
            self.state["systemVolumePercent"] = min(100, max(0, int(round(float(self.state.get("systemVolumePercent", 100))))))
        except (TypeError, ValueError):
            self.state["systemVolumePercent"] = 100
        try:
            self.state["teamNameScale"] = min(1.6, max(0.6, round(float(self.state.get("teamNameScale", 1.0)), 2)))
        except (TypeError, ValueError):
            self.state["teamNameScale"] = 1.0
        if not isinstance(self.state.get("teamNameAutoSize"), bool):
            self.state["teamNameAutoSize"] = parse_bool(self.state.get("teamNameAutoSize"), True)
        for key, fallback in [("musicVolumePercent", 35), ("musicDuckPercent", 30)]:
            try:
                self.state[key] = min(100, max(0, int(round(float(self.state.get(key, fallback))))))
            except (TypeError, ValueError):
                self.state[key] = fallback
        if self.state.get("musicMode") not in {"loop", "sequence", "random"}:
            self.state["musicMode"] = "random"
        if not self.state.get("musicEnabled") or not self.state.get("selectedMusicTrack"):
            self.state["musicPlaying"] = False
        try:
            self.state["musicDuckingUntil"] = max(0, float(self.state.get("musicDuckingUntil") or 0))
        except (TypeError, ValueError):
            self.state["musicDuckingUntil"] = 0
        if not isinstance(self.state.get("rfRemotes"), list):
            self.state["rfRemotes"] = []
        if self.state.get("rfReceiverType") not in {"gpio", "serial", "keyboard"}:
            self.state["rfReceiverType"] = "gpio"
        self.state["rfReceiverSerialDevice"] = str(self.state.get("rfReceiverSerialDevice") or "").strip()[:160]
        self.normalize_rf_remote_slots()
        if not isinstance(self.state.get("rfLastSignal"), dict):
            self.state["rfLastSignal"] = None
        if not isinstance(self.state.get("rfFinishPasswordPending"), bool):
            self.state["rfFinishPasswordPending"] = False
        if not isinstance(self.state.get("rfLearning"), dict):
            self.state["rfLearning"] = None
        if "selectedBallAt" not in self.state:
            self.state["selectedBallAt"] = None
        if self.state.get("finishPassword") in {"0000", "1234"}:
            self.state["finishPassword"] = "9999"
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
        self.reset_match_runtime_on_startup()

    def reset_match_runtime_on_startup(self) -> None:
        duration = int(self.state.get("durationSeconds") or DEFAULT_STATE["durationSeconds"])
        self.state["remainingSeconds"] = duration
        self.state["running"] = False
        self.state["timeExpired"] = False
        self.state["matchFinished"] = False
        self.state["selectedBall"] = 1
        self.state["selectedBallAt"] = None
        self.state["deadline"] = None
        self.state["announcedMinuteWarnings"] = []
        self.state["timerStarted"] = False
        self.state["matchStartedAt"] = None
        self.state["lastTickRemainingSeconds"] = duration
        self.state["tenSecondCountdownId"] = None
        self.state["tenSecondCountdownStartedAt"] = None
        self.state["musicPlaying"] = False
        self.balls = new_balls()
        self.history = []
        self.state["lastMessage"] = f"第{self.state['matchNumber']}场，等待开始"
        self.state["lastUpdated"] = time.time()
        self.save()

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
                **self.preview_state,
                "balls": balls,
                "redTotal": red_total,
                "whiteTotal": white_total,
                "serverTime": time.time(),
                "history": self.history[-30:],
            }

    def emit(self) -> None:
        self.state["lastUpdated"] = time.time()

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

    def normalize_rf_binding(self, value: object) -> dict | None:
        if not isinstance(value, dict):
            return None
        raw = str(value.get("raw") or value.get("code") or "").strip()
        address = str(value.get("address") or "").strip()
        button = str(value.get("button") or "").strip()
        label = str(value.get("label") or raw or f"{address} {button}").strip()
        if not raw and not address and not button:
            return None
        if not raw and address and button:
            raw = f"{address}:{button}"
        return {
            "raw": raw[:80],
            "address": address[:80],
            "button": button[:40],
            "label": label[:80],
        }

    def normalize_rf_remote_slots(self) -> list[dict]:
        raw_slots = self.state.get("rfRemoteSlots")
        if not isinstance(raw_slots, list):
            raw_slots = []
        by_id = {str(slot.get("id")): slot for slot in raw_slots if isinstance(slot, dict)}
        normalized = []
        for default_slot in default_rf_remote_slots():
            existing = by_id.get(default_slot["id"], {})
            bindings = {}
            raw_bindings = existing.get("bindings") if isinstance(existing, dict) else {}
            if isinstance(raw_bindings, dict):
                for action_id, binding in raw_bindings.items():
                    action_id = str(action_id)
                    if action_id not in RF_ACTION_IDS:
                        continue
                    normalized_binding = self.normalize_rf_binding(binding)
                    if normalized_binding:
                        bindings[action_id] = normalized_binding
            normalized.append(
                {
                    "id": default_slot["id"],
                    "name": str(existing.get("name") or default_slot["name"]).strip()[:40] if isinstance(existing, dict) else default_slot["name"],
                    "enabled": parse_bool(existing.get("enabled"), default_slot["enabled"]) if isinstance(existing, dict) else default_slot["enabled"],
                    "bindings": bindings,
                }
            )
        if not any(slot["bindings"] for slot in normalized) and self.state.get("rfRemotes"):
            old_remotes = self.normalize_rf_remotes()
            if old_remotes:
                first = old_remotes[0]
                normalized[0]["name"] = first.get("name") or normalized[0]["name"]
                normalized[0]["enabled"] = parse_bool(first.get("enabled"), True)
                model = RF_REMOTE_MODELS.get(first.get("model"), RF_REMOTE_MODELS["gateball-10key"])
                for button, action_id in model["buttons"].items():
                    if action_id not in RF_ACTION_IDS:
                        continue
                    normalized[0]["bindings"][action_id] = {
                        "raw": f"{first['address']}:{button}",
                        "address": first["address"],
                        "button": button,
                        "label": button,
                    }
        self.state["rfRemoteSlots"] = normalized
        return normalized

    def normalize_rf_remotes(self) -> list[dict]:
        remotes = self.state.get("rfRemotes")
        if not isinstance(remotes, list):
            remotes = []
        normalized = []
        seen = set()
        for index, remote in enumerate(remotes):
            if not isinstance(remote, dict):
                continue
            address = str(remote.get("address", "")).strip()
            if not address or address in seen:
                continue
            seen.add(address)
            remote_id = str(remote.get("id") or f"rf-{address}").strip()
            normalized.append(
                {
                    "id": remote_id,
                    "name": str(remote.get("name") or f"Remote {index + 1}").strip()[:40],
                    "enabled": parse_bool(remote.get("enabled"), True),
                    "model": str(remote.get("model") or self.state.get("rfRemoteModel") or "gateball-10key"),
                    "address": address,
                    "lastSeenAt": remote.get("lastSeenAt"),
                }
            )
        self.state["rfRemotes"] = normalized
        return normalized

    def record_rf_signal(self, *, raw: str, address: str, button: str, remote: dict | None, action_id: str, status: str) -> dict:
        now = time.time()
        self.state["rfLastSignal"] = {
            "id": f"{now:.6f}",
            "receivedAt": now,
            "raw": raw,
            "address": address,
            "button": button,
            "remoteId": remote.get("id") if remote else None,
            "remoteName": remote.get("name") if remote else None,
            "action": action_id,
            "status": status,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        if remote:
            remote["lastSeenAt"] = self.state["rfLastSignal"]["time"]
        return self.state["rfLastSignal"]

    def rf_learning_status(self) -> dict | None:
        learning = self.state.get("rfLearning")
        if not isinstance(learning, dict):
            return None
        expires_at = float(learning.get("expiresAt") or 0)
        if expires_at and time.time() > expires_at:
            self.state["rfLearning"] = None
            return None
        return learning

    def handle_rf_signal(self, payload: dict) -> dict:
        raw = str(payload.get("raw") or payload.get("code") or "").strip()
        address = str(payload.get("address") or "").strip()
        button = str(payload.get("button") or "").strip()
        if not address and raw:
            address = raw[:-1] if len(raw) > 1 else raw
        if not button and raw:
            button = raw[-1:]
        learning = self.rf_learning_status()
        if learning and not learning.get("signal"):
            signal = self.record_rf_signal(raw=raw, address=address, button=button, remote=None, action_id="", status="learning")
            learning["signal"] = signal
            self.state["rfLearning"] = learning
            self.save()
            self.emit()
            return {"ok": True, "message": "learning", "state": self.snapshot()}
        slots = self.normalize_rf_remote_slots()
        remote = None
        action_id = ""
        status = "ignored"
        if not self.state.get("rfRemoteEnabled"):
            self.state["rfRemoteEnabled"] = True
        if self.state.get("rfRemoteEnabled"):
            for slot in slots:
                if not slot.get("enabled"):
                    continue
                for candidate_action, binding in slot.get("bindings", {}).items():
                    if raw and binding.get("raw") == raw:
                        remote = slot
                        action_id = candidate_action
                        break
                    if address and button and binding.get("address") == address and binding.get("button") == button:
                        remote = slot
                        action_id = candidate_action
                        break
                if remote:
                    break
            if not remote:
                status = "unknown_remote"
            elif not action_id:
                status = "unknown_button"
            if action_id == "finish_dialog":
                self.state["rfFinishPasswordPending"] = True
                status = "finish_requires_password"
            elif self.state.get("rfFinishPasswordPending") and (
                re.fullmatch(r"ball_(?:[1-9]|10)", action_id or "") or action_id == "toggle_music"
            ):
                status = "finish_password_digit"
            elif action_id == "toggle_music":
                now = time.time()
                duplicate_music_signal = raw and raw == self.last_rf_music_raw and (now - self.last_rf_music_at) < 0.7
                if duplicate_music_signal:
                    status = "duplicate"
                else:
                    self.last_rf_music_raw = raw
                    self.last_rf_music_at = now
                    status = "executed"
                    self.action(RF_ACTION_PAYLOADS[action_id])
            elif action_id in RF_ACTION_PAYLOADS:
                status = "executed"
                self.action(RF_ACTION_PAYLOADS[action_id])
            elif action_id:
                status = "unknown_button"
        self.record_rf_signal(raw=raw, address=address, button=button, remote=remote, action_id=action_id, status=status)
        self.save()
        self.emit()
        return {"ok": status in {"executed", "finish_requires_password", "finish_password_digit"}, "message": status, "state": self.snapshot()}

    def action(self, payload: dict) -> dict:
        self.tick()
        action = payload.get("action")
        message = ""

        if action == "simulate_rf_signal":
            return self.handle_rf_signal(payload)

        if action == "clear_rf_last_signal":
            self.state["rfLastSignal"] = None
            self.save()
            self.emit()
            return {"ok": True, "message": "RF signal cleared", "state": self.snapshot()}

        if action == "begin_finish_dialog":
            self.state["rfFinishPasswordPending"] = True
            self.save()
            self.emit()
            return {"ok": True, "message": "finish dialog opened", "state": self.snapshot()}

        if action == "cancel_finish_dialog":
            self.state["rfFinishPasswordPending"] = False
            self.save()
            self.emit()
            return {"ok": True, "message": "finish dialog cancelled", "state": self.snapshot()}

        if action == "set_music_ducking":
            active = parse_bool(payload.get("active"))
            if active:
                try:
                    duration_ms = min(30000, max(300, int(float(payload.get("durationMs") or 5000))))
                except (TypeError, ValueError):
                    duration_ms = 5000
                self.state["musicDuckingUntil"] = time.time() + (duration_ms / 1000)
            else:
                self.state["musicDuckingUntil"] = 0
            self.emit()
            return {"ok": True, "message": "music ducking updated", "state": self.snapshot()}

        if action == "begin_rf_learning":
            now = time.time()
            self.state["rfLearning"] = {
                "id": f"{now:.6f}",
                "slotId": str(payload.get("slotId") or ""),
                "actionId": str(payload.get("bindingAction") or ""),
                "startedAt": now,
                "expiresAt": now + 10,
                "signal": None,
            }
            self.save()
            self.emit()
            return {"ok": True, "message": "RF learning started", "state": self.snapshot()}

        if action == "cancel_rf_learning":
            self.state["rfLearning"] = None
            self.save()
            self.emit()
            return {"ok": True, "message": "RF learning cancelled", "state": self.snapshot()}

        if action == "update_rf_settings":
            if payload.get("password") != self.state["settingsPassword"]:
                message = "密码错误"
            else:
                self.state["rfRemoteEnabled"] = parse_bool(payload.get("rfRemoteEnabled"))
                receiver_type = str(payload.get("rfReceiverType") or self.state.get("rfReceiverType") or "gpio")
                self.state["rfReceiverType"] = receiver_type if receiver_type in {"gpio", "serial", "keyboard"} else "gpio"
                try:
                    gpio = int(payload.get("rfReceiverGpio", self.state.get("rfReceiverGpio", 27)))
                    self.state["rfReceiverGpio"] = min(27, max(2, gpio))
                except (TypeError, ValueError):
                    pass
                self.state["rfReceiverSerialDevice"] = str(payload.get("rfReceiverSerialDevice") or "").strip()[:160]
                model = str(payload.get("rfRemoteModel") or "gateball-10key")
                self.state["rfRemoteModel"] = model if model in RF_REMOTE_MODELS else "gateball-10key"
                message = "RF remote settings saved"
                self.state["lastMessage"] = message
                self.record("rf_settings", None, message)
            self.save()
            return {"ok": message != "密码错误", "message": message, "state": self.snapshot()}

        if action == "update_rf_remote_slot":
            if payload.get("password") != self.state["settingsPassword"]:
                message = "密码错误"
            else:
                slot_id = str(payload.get("slotId") or "").strip()
                slots = self.normalize_rf_remote_slots()
                slot = next((item for item in slots if item["id"] == slot_id), None)
                if not slot:
                    message = "遥控器不存在"
                else:
                    slot["name"] = str(payload.get("name") or slot["name"]).strip()[:40]
                    slot["enabled"] = parse_bool(payload.get("enabled"))
                    bindings = {}
                    raw_bindings = payload.get("bindings")
                    if isinstance(raw_bindings, dict):
                        for action_id, binding in raw_bindings.items():
                            action_id = str(action_id)
                            if action_id not in RF_ACTION_IDS:
                                continue
                            normalized_binding = self.normalize_rf_binding(binding)
                            if normalized_binding:
                                bindings[action_id] = normalized_binding
                    slot["bindings"] = bindings
                    self.state["rfRemoteSlots"] = slots
                    message = "遥控器设置已保存"
                    self.state["lastMessage"] = message
                    self.record("rf_remote", None, message)
            self.save()
            return {"ok": message == "遥控器设置已保存", "message": message, "state": self.snapshot()}

        if action == "clear_rf_remote_slot":
            if payload.get("password") != self.state["settingsPassword"]:
                message = "密码错误"
            else:
                slot_id = str(payload.get("slotId") or "").strip()
                slots = self.normalize_rf_remote_slots()
                slot = next((item for item in slots if item["id"] == slot_id), None)
                if slot:
                    slot["bindings"] = {}
                    self.state["rfRemoteSlots"] = slots
                    message = "遥控器按键已清除"
                    self.state["lastMessage"] = message
                    self.record("rf_remote", None, message)
                else:
                    message = "遥控器不存在"
            self.save()
            return {"ok": message == "遥控器按键已清除", "message": message, "state": self.snapshot()}

        if action == "update_keyboard_settings":
            if payload.get("password") != self.state["settingsPassword"]:
                message = "密码错误"
            else:
                self.state["keyboardInputEnabled"] = parse_bool(payload.get("keyboardInputEnabled"))
                message = "键盘设置已保存"
                self.state["lastMessage"] = message
                self.record("keyboard_settings", None, message)
            self.save()
            return {"ok": message == "键盘设置已保存", "message": message, "state": self.snapshot()}

        if action == "clear_key_bindings":
            if payload.get("password") != self.state["settingsPassword"]:
                message = "密码错误"
            else:
                self.state["keyBindings"] = {}
                message = "键盘映射已恢复默认"
                self.state["lastMessage"] = message
                self.record("keyboard_settings", None, message)
            self.save()
            return {"ok": message == "键盘映射已恢复默认", "message": message, "state": self.snapshot()}

        if action == "add_rf_remote":
            if payload.get("password") != self.state["settingsPassword"]:
                message = "密码错误"
            else:
                address = str(payload.get("address", "")).strip()
                if not address:
                    message = "RF address is required"
                else:
                    remotes = self.normalize_rf_remotes()
                    existing = next((item for item in remotes if item["address"] == address), None)
                    model = str(payload.get("model") or self.state.get("rfRemoteModel") or "gateball-10key")
                    model = model if model in RF_REMOTE_MODELS else "gateball-10key"
                    if existing:
                        existing["name"] = str(payload.get("name") or existing["name"]).strip()[:40]
                        existing["enabled"] = parse_bool(payload.get("enabled"), True)
                        existing["model"] = model
                    else:
                        remotes.append(
                            {
                                "id": f"rf-{int(time.time() * 1000)}",
                                "name": str(payload.get("name") or f"Remote {len(remotes) + 1}").strip()[:40],
                                "enabled": parse_bool(payload.get("enabled"), True),
                                "model": model,
                                "address": address,
                                "lastSeenAt": None,
                            }
                        )
                    self.state["rfRemotes"] = remotes
                    message = "RF remote saved"
                    self.state["lastMessage"] = message
                    self.record("rf_remote", None, message)
            self.save()
            return {"ok": message != "密码错误" and "required" not in message, "message": message, "state": self.snapshot()}

        if action == "update_rf_remote":
            if payload.get("password") != self.state["settingsPassword"]:
                message = "密码错误"
            else:
                remote_id = str(payload.get("id", "")).strip()
                remote = next((item for item in self.normalize_rf_remotes() if item["id"] == remote_id), None)
                if remote:
                    if "name" in payload:
                        remote["name"] = str(payload.get("name") or remote["name"]).strip()[:40]
                    if "enabled" in payload:
                        remote["enabled"] = parse_bool(payload.get("enabled"))
                    message = "RF remote updated"
                    self.state["lastMessage"] = message
                    self.record("rf_remote", None, message)
                else:
                    message = "RF remote not found"
            self.save()
            return {"ok": message == "RF remote updated", "message": message, "state": self.snapshot()}

        if action == "delete_rf_remote":
            if payload.get("password") != self.state["settingsPassword"]:
                message = "密码错误"
            else:
                remote_id = str(payload.get("id", "")).strip()
                self.state["rfRemotes"] = [remote for remote in self.normalize_rf_remotes() if remote["id"] != remote_id]
                message = "RF remote deleted"
                self.state["lastMessage"] = message
                self.record("rf_remote", None, message)
            self.save()
            return {"ok": message == "RF remote deleted", "message": message, "state": self.snapshot()}

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
            elif not self.state["running"] and not self.state["allowScoringWhenPaused"] and not self.state["timeExpired"]:
                message = "暂停期间不能计分"
            else:
                number = int(self.state["selectedBall"])
                message = self.balls[number].undo()
                self.state["lastMessage"] = message
                self.record("undo", number, message)

        elif action == "toggle_timer":
            if self.state.get("matchFinished"):
                message = self.reset_match()
                return {"ok": True, "message": message, "state": self.snapshot()}
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

        elif action == "toggle_music":
            if self.state.get("musicEnabled") and self.state.get("selectedMusicTrack"):
                now = time.time()
                try:
                    resume_to_next = (now - float(self.state.get("lastMusicToggleAt") or 0)) <= 5.0
                except (TypeError, ValueError):
                    resume_to_next = False
                if self.state.get("musicPlaying"):
                    self.state["musicPlaying"] = False
                    self.state["lastMusicToggleAt"] = now
                    message = "音乐暂停"
                elif resume_to_next:
                    next_track_id = next_music_track_id(
                        str(self.state.get("selectedMusicTrack") or ""),
                        str(self.state.get("musicMode") or "loop"),
                    )
                    if next_track_id:
                        self.state["selectedMusicTrack"] = next_track_id
                    self.state["musicPlaying"] = True
                    self.state["lastMusicToggleAt"] = 0
                    message = "音乐下一首"
                else:
                    self.state["musicPlaying"] = True
                    self.state["lastMusicToggleAt"] = 0
                    message = "音乐播放"
            else:
                self.state["musicPlaying"] = False
                self.state["lastMusicToggleAt"] = 0
                message = "未启用背景音乐"
            self.state["lastMessage"] = message
            self.record("toggle_music", None, message)

        elif action == "ten_second_countdown":
            now = time.time()
            started_at = self.state.get("tenSecondCountdownStartedAt")
            try:
                countdown_active = bool(self.state.get("tenSecondCountdownId")) and (now - float(started_at)) < 10
            except (TypeError, ValueError):
                countdown_active = False
            if countdown_active:
                message = "10秒倒计时已停止"
                self.state["tenSecondCountdownId"] = None
                self.state["tenSecondCountdownStartedAt"] = None
                self.state["lastMessage"] = message
                self.record("cancel_ten_second_countdown", None, message)
            else:
                message = "10秒倒计时"
                event_id = f"{now:.6f}"
                self.state["tenSecondCountdownId"] = event_id
                self.state["tenSecondCountdownStartedAt"] = now
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
                self.state["rfFinishPasswordPending"] = False
                finished_snapshot = self.snapshot()
                if not self.state.get("matchFinished"):
                    results_store.save_match(finished_snapshot)
                    self.state["running"] = False
                    self.state["deadline"] = None
                    self.state["matchFinished"] = True
                    if self.state.get("musicStopWhenMatchEnds", False):
                        self.state["musicPlaying"] = False
                    message = "match finished"
                    self.state["lastMessage"] = message
                    self.record("finish", None, message)
                    self.save()
                else:
                    message = self.state.get("lastMessage") or "match finished"
                return {"ok": True, "message": message, "finishedMatch": finished_snapshot, "state": self.snapshot()}
            else:
                self.state["rfFinishPasswordPending"] = True
                message = "密码错误"
                self.state["lastMessage"] = message
                self.record("finish_denied", None, message)

        elif action == "advance_to_next_match":
            if self.state.get("matchFinished") or self.state.get("timeExpired"):
                message = self.reset_match()
                return {"ok": True, "message": message, "state": self.snapshot()}
            message = self.state.get("lastMessage", "")

        elif action == "update_settings":
            if payload.get("password") != self.state["settingsPassword"]:
                message = "密码错误"
            else:
                hotspot_changed = "hotspotSsid" in payload or "hotspotPassword" in payload
                for key in ["allowScoringWhenPaused", "weatherLocation", "courtName", "hotspotSsid"]:
                    if key in payload:
                        self.state[key] = str(payload[key]).strip() if key != "allowScoringWhenPaused" else payload[key]
                        if key == "weatherLocation":
                            WEATHER_CACHE["timestamp"] = 0.0
                if "titleColor" in payload:
                    color = str(payload["titleColor"]).strip()
                    self.state["titleColor"] = color if re.fullmatch(r"#[0-9a-fA-F]{6}", color) else DEFAULT_STATE["titleColor"]
                if "hotspotPassword" in payload:
                    password = str(payload["hotspotPassword"]).strip()
                    if len(password) >= 8:
                        self.state["hotspotPassword"] = password[:63]
                if "showBootWifiInfo" in payload:
                    self.state["showBootWifiInfo"] = parse_bool(payload.get("showBootWifiInfo"), True)
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
                if "systemVolumePercent" in payload:
                    try:
                        volume = int(round(float(payload["systemVolumePercent"])))
                        self.state["systemVolumePercent"] = min(100, max(0, volume))
                        set_system_volume_percent(self.state["systemVolumePercent"])
                    except (TypeError, ValueError):
                        pass
                if "musicEnabled" in payload:
                    self.state["musicEnabled"] = bool(payload["musicEnabled"])
                if "musicAutoPlayDuringMatch" in payload:
                    self.state["musicAutoPlayDuringMatch"] = bool(payload["musicAutoPlayDuringMatch"])
                if "musicStopWhenMatchEnds" in payload:
                    self.state["musicStopWhenMatchEnds"] = bool(payload["musicStopWhenMatchEnds"])
                if "musicDuckDuringSpeech" in payload:
                    self.state["musicDuckDuringSpeech"] = bool(payload["musicDuckDuringSpeech"])
                if "selectedMusicTrack" in payload:
                    track_id = str(payload.get("selectedMusicTrack") or "")
                    self.state["selectedMusicTrack"] = track_id if not track_id or resolve_music_track(track_id) else ""
                if "musicMode" in payload:
                    mode = str(payload.get("musicMode") or "random")
                    self.state["musicMode"] = mode if mode in {"loop", "sequence", "random"} else "random"
                if "musicVolumePercent" in payload:
                    try:
                        volume = int(round(float(payload["musicVolumePercent"])))
                        self.state["musicVolumePercent"] = min(100, max(0, volume))
                    except (TypeError, ValueError):
                        pass
                if "musicDuckPercent" in payload:
                    try:
                        duck = int(round(float(payload["musicDuckPercent"])))
                        self.state["musicDuckPercent"] = min(80, max(10, duck))
                    except (TypeError, ValueError):
                        pass
                if not self.state.get("musicEnabled") or not self.state.get("selectedMusicTrack"):
                    self.state["musicPlaying"] = False
                if "titleFontScale" in payload:
                    try:
                        scale = round(float(payload["titleFontScale"]), 2)
                        self.state["titleFontScale"] = min(1.4, max(0.7, scale))
                    except (TypeError, ValueError):
                        pass
                if "teamNameScale" in payload:
                    try:
                        scale = round(float(payload["teamNameScale"]), 2)
                        self.state["teamNameScale"] = min(1.6, max(0.6, scale))
                    except (TypeError, ValueError):
                        pass
                if "teamNameAutoSize" in payload:
                    self.state["teamNameAutoSize"] = bool(payload["teamNameAutoSize"])
                if "tableMarkerAutoSize" in payload:
                    self.state["tableMarkerAutoSize"] = bool(payload["tableMarkerAutoSize"])
                if "tableMarkerScale" in payload:
                    try:
                        scale = round(float(payload["tableMarkerScale"]), 2)
                        self.state["tableMarkerScale"] = min(1.8, max(0.5, scale))
                    except (TypeError, ValueError):
                        pass
                self.preview_state.clear()
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
                network_message = ""
                if hotspot_changed:
                    hotspot_result = configure_hotspot(self.state.get("hotspotSsid", ""), self.state.get("hotspotPassword", ""))
                    if not hotspot_result.get("ok"):
                        network_message = f"；{hotspot_result.get('message') or '热点同步失败'}"
                    elif hotspot_result.get("supported") is False:
                        network_message = "；热点配置已保存，当前系统未自动应用"
                message = f"设置已保存{network_message}"
                self.state["lastMessage"] = message
                self.record("settings", None, message)

        elif action == "delete_music_item":
            if payload.get("password") != self.state.get("settingsPassword"):
                return {"ok": False, "message": "密码错误", "state": self.snapshot()}
            item_id = str(payload.get("musicItemId") or "")
            resolved = resolve_music_item(item_id)
            if not resolved:
                return {"ok": False, "message": "音乐项目不存在", "state": self.snapshot()}
            item_type, target = resolved
            selected_target = resolve_music_track(str(self.state.get("selectedMusicTrack") or ""))
            try:
                if item_type == "directory":
                    if selected_target:
                        try:
                            selected_target.relative_to(target)
                            self.state["selectedMusicTrack"] = ""
                            self.state["musicPlaying"] = False
                        except ValueError:
                            pass
                    shutil.rmtree(target)
                    message = "音乐目录已删除"
                else:
                    if selected_target and selected_target == target:
                        self.state["selectedMusicTrack"] = ""
                        self.state["musicPlaying"] = False
                    target.unlink()
                    message = "音乐文件已删除"
            except OSError as exc:
                return {"ok": False, "message": f"删除失败: {exc}", "state": self.snapshot()}
            MUSIC_TRACKS_CACHE["timestamp"] = 0.0
            MUSIC_TRACKS_CACHE["tracks"] = []
            self.state["lastMessage"] = message
            self.state["lastUpdated"] = time.time()
            self.save()
            self.emit()
            self.record("settings", None, message)
            return {"ok": True, "message": message, "state": self.snapshot()}

        elif action == "preview_title_style":
            if "titleColor" in payload:
                color = str(payload["titleColor"]).strip()
                self.preview_state["titleColor"] = color if re.fullmatch(r"#[0-9a-fA-F]{6}", color) else DEFAULT_STATE["titleColor"]
            if "titleFontScale" in payload:
                try:
                    scale = round(float(payload["titleFontScale"]), 2)
                    self.preview_state["titleFontScale"] = min(1.4, max(0.7, scale))
                except (TypeError, ValueError):
                    pass
            if "teamNameScale" in payload:
                try:
                    scale = round(float(payload["teamNameScale"]), 2)
                    self.preview_state["teamNameScale"] = min(1.6, max(0.6, scale))
                except (TypeError, ValueError):
                    pass
            if "teamNameAutoSize" in payload:
                self.preview_state["teamNameAutoSize"] = bool(payload["teamNameAutoSize"])
            if "tableMarkerAutoSize" in payload:
                self.preview_state["tableMarkerAutoSize"] = bool(payload["tableMarkerAutoSize"])
            if "tableMarkerScale" in payload:
                try:
                    scale = round(float(payload["tableMarkerScale"]), 2)
                    self.preview_state["tableMarkerScale"] = min(1.8, max(0.5, scale))
                except (TypeError, ValueError):
                    pass
            self.state["lastUpdated"] = time.time()
            message = self.state.get("lastMessage", "")
            return {"ok": True, "message": message, "state": self.snapshot()}

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
rf_listener_started = False
rf_signal_queue: SimpleQueue[dict] = SimpleQueue()


def enqueue_rf_signal(payload: dict) -> None:
    rf_signal_queue.put(payload)


def rf_signal_worker_loop() -> None:
    while True:
        try:
            store.action(rf_signal_queue.get())
        except Exception as exc:
            print(f"RF action error: {exc}")


def split_rf_code(code: object) -> tuple[str, str]:
    text = str(code)
    if len(text) <= 1:
        return text, ""
    return text[:-1], text[-1]


def rf_payload_from_code(code: object, *, address: str = "", button: str = "") -> dict:
    raw = str(code).strip()
    if not address and not button:
        address, button = split_rf_code(raw)
    return {
        "action": "simulate_rf_signal",
        "raw": raw,
        "address": str(address or "").strip(),
        "button": str(button or "").strip(),
    }


def rf_payload_from_24bit_code(code: int) -> dict:
    address = (code >> 8) & 0xFFFF
    button = code & 0xFF
    return rf_payload_from_code(f"0x{code:06X}", address=f"0x{address:04X}", button=f"0x{button:02X}")


def lgpio_tick_delta_us(previous_tick: int, tick: int) -> int:
    delta = int(tick - previous_tick)
    if delta < 0:
        delta = int((tick - previous_tick) & 0xFFFFFFFF)
    if delta > 100_000:
        return max(1, int(delta / 1000))
    return delta


def claim_lgpio_alert(lgpio, handle: int, gpio: int) -> None:
    try:
        lgpio.gpio_claim_alert(handle, gpio, lgpio.BOTH_EDGES)
        return
    except TypeError:
        pass
    lgpio.gpio_claim_alert(handle, 0, lgpio.BOTH_EDGES, gpio, -1)


def rf_payload_from_serial_line(line: str) -> dict | None:
    text = line.strip()
    if not text:
        return None
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {}
        raw = data.get("raw") or data.get("code") or data.get("value") or ""
        if raw or data.get("address") or data.get("button"):
            return rf_payload_from_code(raw, address=str(data.get("address") or ""), button=str(data.get("button") or ""))
    parts = re.split(r"[:：,\s]+", text)
    parts = [part for part in parts if part]
    if len(parts) >= 2:
        return rf_payload_from_code(text, address=parts[0], button=" ".join(parts[1:]))
    return rf_payload_from_code(text)


def cleanup_rf_device(device: object | None) -> None:
    if not device:
        return
    cleanup = getattr(device, "cleanup", None)
    close = getattr(device, "close", None)
    try:
        if callable(cleanup):
            cleanup()
        elif callable(close):
            close()
    except Exception:
        pass


@dataclass(frozen=True)
class RfPwmFrame:
    code: int
    short_us: float
    long_us: float


class RfPwm24Decoder:
    SYNC_MIN_US = 8_000
    SYNC_MAX_US = 18_000
    SHORT_MIN_US = 180
    SHORT_MAX_US = 700
    LONG_MIN_US = 800
    LONG_MAX_US = 1_700

    def __init__(self) -> None:
        self._collecting = False
        self._runs: list[tuple[int, float]] = []

    def feed_transition(self, finished_level: int, duration_us: int, new_level: int) -> RfPwmFrame | None:
        if (
            finished_level == 0
            and new_level == 1
            and self.SYNC_MIN_US <= duration_us <= self.SYNC_MAX_US
        ):
            self._collecting = True
            self._runs = []
            return None
        if not self._collecting:
            return None
        self._runs.append((finished_level, float(duration_us)))
        if len(self._runs) < 48:
            return None
        runs = self._runs
        self._collecting = False
        self._runs = []
        return self._decode_runs(runs)

    def _decode_runs(self, runs: list[tuple[int, float]]) -> RfPwmFrame | None:
        bits: list[str] = []
        shorts: list[float] = []
        longs: list[float] = []
        for i in range(0, 48, 2):
            high_level, high_us = runs[i]
            low_level, low_us = runs[i + 1]
            if high_level != 1 or low_level != 0:
                return None
            high_short = self.SHORT_MIN_US <= high_us <= self.SHORT_MAX_US
            low_short = self.SHORT_MIN_US <= low_us <= self.SHORT_MAX_US
            high_long = self.LONG_MIN_US <= high_us <= self.LONG_MAX_US
            low_long = self.LONG_MIN_US <= low_us <= self.LONG_MAX_US
            if high_short and low_long:
                bits.append("0")
                shorts.append(high_us)
                longs.append(low_us)
            elif high_long and low_short:
                bits.append("1")
                longs.append(high_us)
                shorts.append(low_us)
            else:
                return None
        return RfPwmFrame(code=int("".join(bits), 2), short_us=sum(shorts) / len(shorts), long_us=sum(longs) / len(longs))


class RfRepeatFilter:
    def __init__(self, repeats_required: int = 2, repeat_window_s: float = 0.25):
        self.repeats_required = repeats_required
        self.repeat_window_s = repeat_window_s
        self._candidate: int | None = None
        self._count = 0
        self._last_frame_time = 0.0
        self._emitted = False

    def accept(self, frame: RfPwmFrame) -> bool:
        now = time.monotonic()
        same_group = frame.code == self._candidate and now - self._last_frame_time <= self.repeat_window_s
        if same_group:
            self._count += 1
        else:
            self._candidate = frame.code
            self._count = 1
            self._emitted = False
        self._last_frame_time = now
        if self._count >= self.repeats_required and not self._emitted:
            self._emitted = True
            return True
        return False


class LgpioRfReceiver:
    def __init__(self, gpio: int, on_code) -> None:
        import lgpio  # type: ignore

        self.lgpio = lgpio
        self.handle = lgpio.gpiochip_open(0)
        claim_lgpio_alert(lgpio, self.handle, gpio)
        self.decoder = RfPwm24Decoder()
        self.inverted_decoder = RfPwm24Decoder()
        self.repeat_filter = RfRepeatFilter()
        self.inverted_repeat_filter = RfRepeatFilter()
        self.last_tick = None
        self.last_level = None
        self.on_code = on_code
        self.callback = lgpio.callback(self.handle, gpio, lgpio.BOTH_EDGES, self._on_edge)

    def _on_edge(self, _chip: int, _gpio: int, level: int, tick: int) -> None:
        if self.last_tick is None:
            self.last_tick = tick
            self.last_level = int(level)
            return
        duration = lgpio_tick_delta_us(self.last_tick, tick)
        finished_level = int(self.last_level if self.last_level is not None else 1 - int(level))
        self.last_tick = tick
        self.last_level = int(level)
        frame = self.decoder.feed_transition(finished_level, duration, int(level))
        if frame is not None and self.repeat_filter.accept(frame):
            self.on_code(frame.code)
        inverted_frame = self.inverted_decoder.feed_transition(1 - finished_level, duration, 1 - int(level))
        if inverted_frame is not None and self.inverted_repeat_filter.accept(inverted_frame):
            self.on_code(inverted_frame.code)

    def cleanup(self) -> None:
        try:
            self.callback.cancel()
        finally:
            self.lgpio.gpiochip_close(self.handle)


def rf_listener_loop() -> None:
    rfdevice = None
    serial_file = None
    rf_device_class = None
    rpi_rf_missing_logged = False
    lgpio_missing_logged = False
    active_gpio = None
    active_serial_device = ""
    active_mode = ""
    last_timestamp = None
    last_code = None
    last_at = 0.0
    while True:
        try:
            enabled = bool(store.state.get("rfRemoteEnabled"))
            receiver_type = str(store.state.get("rfReceiverType") or "gpio")
            gpio = int(store.state.get("rfReceiverGpio", 27))
            serial_device = str(store.state.get("rfReceiverSerialDevice") or "").strip()
            if not enabled or receiver_type == "keyboard":
                if rfdevice or serial_file:
                    cleanup_rf_device(rfdevice)
                    cleanup_rf_device(serial_file)
                    rfdevice = None
                    serial_file = None
                    active_gpio = None
                    active_serial_device = ""
                    active_mode = ""
                    print("RF listener paused")
                time.sleep(1.0)
                continue
            if receiver_type == "gpio":
                if serial_file:
                    cleanup_rf_device(serial_file)
                    serial_file = None
                    active_serial_device = ""
                if rfdevice is None or active_mode not in {"gpio", "gpio-rpi-rf"} or active_gpio != gpio:
                    cleanup_rf_device(rfdevice)
                    try:
                        rfdevice = LgpioRfReceiver(gpio, lambda code: enqueue_rf_signal(rf_payload_from_24bit_code(code)))
                        active_mode = "gpio"
                        active_gpio = gpio
                        last_timestamp = None
                        print(f"RF GPIO listener active with lgpio on BCM GPIO {gpio}")
                    except Exception as exc:
                        cleanup_rf_device(rfdevice)
                        rfdevice = None
                        if not lgpio_missing_logged:
                            print(f"RF GPIO lgpio listener unavailable on BCM GPIO {gpio}: {exc}")
                            lgpio_missing_logged = True
                        if rf_device_class is None:
                            try:
                                from rpi_rf import RFDevice  # type: ignore
                                rf_device_class = RFDevice
                            except ImportError:
                                if not rpi_rf_missing_logged:
                                    print("RF GPIO listener disabled: neither lgpio nor rpi-rf is available")
                                    rpi_rf_missing_logged = True
                                time.sleep(5.0)
                                continue
                        try:
                            rfdevice = rf_device_class(gpio)
                            rfdevice.enable_rx()
                            active_mode = "gpio-rpi-rf"
                            active_gpio = gpio
                            last_timestamp = None
                            print(f"RF GPIO listener active with rpi-rf on BCM GPIO {gpio}")
                        except Exception as exc:
                            cleanup_rf_device(rfdevice)
                            rfdevice = None
                            active_mode = ""
                            active_gpio = None
                            print(f"RF GPIO listener disabled: rpi-rf cannot start on BCM GPIO {gpio}: {exc}")
                            time.sleep(5.0)
                            continue
                if active_mode == "gpio-rpi-rf":
                    timestamp = rfdevice.rx_code_timestamp
                    if timestamp and timestamp != last_timestamp:
                        last_timestamp = timestamp
                        now = time.monotonic()
                        code = rfdevice.rx_code
                        if code != last_code or (now - last_at) >= 0.3:
                            enqueue_rf_signal(rf_payload_from_code(code))
                            last_code = code
                            last_at = now
                    time.sleep(0.01)
                else:
                    time.sleep(1.0)
                continue
            if receiver_type == "serial":
                if rfdevice:
                    cleanup_rf_device(rfdevice)
                    rfdevice = None
                active_gpio = None
                if not serial_device:
                    cleanup_rf_device(serial_file)
                    serial_file = None
                    active_serial_device = ""
                    time.sleep(1.0)
                    continue
                if serial_file is None or active_mode != "serial" or active_serial_device != serial_device:
                    cleanup_rf_device(serial_file)
                    serial_file = open(serial_device, "r", encoding="utf-8", errors="replace", buffering=1)
                    active_mode = "serial"
                    active_serial_device = serial_device
                    print(f"RF serial listener active on {serial_device}")
                readable, _, _ = select.select([serial_file], [], [], 0.25)
                if readable:
                    payload = rf_payload_from_serial_line(serial_file.readline())
                    if payload:
                        enqueue_rf_signal(payload)
                continue
            time.sleep(1.0)
        except Exception as exc:
            print(f"RF listener error: {exc}")
            cleanup_rf_device(rfdevice)
            cleanup_rf_device(serial_file)
            rfdevice = None
            serial_file = None
            active_gpio = None
            active_serial_device = ""
            active_mode = ""
            time.sleep(3.0)


def start_rf_listener() -> None:
    global rf_listener_started
    if rf_listener_started:
        return
    rf_listener_started = True
    Thread(target=rf_signal_worker_loop, name="gateball-rf-worker", daemon=True).start()
    Thread(target=rf_listener_loop, name="gateball-rf-listener", daemon=True).start()


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
    cached_payload = WEATHER_CACHE.get("payload", {"ok": False})
    cache_seconds = 1800 if cached_payload.get("ok") else 30
    if now - float(WEATHER_CACHE.get("timestamp", 0)) < cache_seconds:
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
    except Exception as exc:
        payload = {"ok": False, "message": str(exc)}

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
            params = parse_qs(urlparse(self.path).query)
            return_target = params.get("return", [""])[0]
            location = "/remote?settings=1"
            if return_target == "scoreboard":
                location += "&return=scoreboard"
            self.send_response(302)
            self.send_header("Location", location)
            self.end_headers()
        elif path == "/api/events":
            self.send_events()
        elif path == "/api/state":
            self.send_json(store.snapshot())
        elif path == "/api/rf/last":
            self.send_json({"ok": True, "signal": store.state.get("rfLastSignal"), "serverTime": time.time()})
        elif path == "/api/rf/learning":
            self.send_json({"ok": True, "learning": store.rf_learning_status(), "serverTime": time.time()})
        elif path == "/api/network/status":
            self.send_json(network_status(store.state))
        elif path == "/api/network/scan":
            self.send_json(scan_wifi_networks())
        elif path == "/api/music/tracks":
            tracks, items = list_music_items()
            self.send_json({"ok": True, "tracks": tracks, "items": items})
        elif path == "/api/music/file":
            params = parse_qs(urlparse(self.path).query)
            target = resolve_music_track(params.get("id", [""])[0])
            if target:
                self.serve_file(target)
            else:
                self.send_error(404)
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
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(data)
            self.wfile.flush()
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
                snapshot.get("titleColor"),
                snapshot.get("titleFontScale"),
                snapshot.get("teamNameScale"),
                snapshot.get("tableMarkerAutoSize"),
                snapshot.get("tableMarkerScale"),
                snapshot.get("musicDuckingUntil"),
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
    start_rf_listener()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Gateball web prototype: http://127.0.0.1:{PORT}/scoreboard")
    print(f"Phone remote: http://127.0.0.1:{PORT}/remote")
    print(f"Settings: http://127.0.0.1:{PORT}/set")
    server.serve_forever()


if __name__ == "__main__":
    main()
