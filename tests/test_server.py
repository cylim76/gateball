"""Isolated regressions; no real device, production database or network changes."""
from __future__ import annotations

import ast
import copy
import http.client
import json
import sqlite3
import sys
import tempfile
import threading
import types
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))


def load_server():
    path = ROOT / "web/server.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    tree.body = [node for node in tree.body if not (
        isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in {"store", "results_store"}
            for target in node.targets))]
    module = types.ModuleType("gateball_test_server")
    module.__file__ = str(path)
    sys.modules[module.__name__] = module
    exec(compile(tree, str(path), "exec"), module.__dict__)
    return module


server = load_server()
DEFAULTS = copy.deepcopy(server.DEFAULT_STATE)
APPLY_AUDIO_OUTPUT_MODE = server.apply_audio_output_mode
SET_SYSTEM_VOLUME_PERCENT = server.set_system_volume_percent


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gateball-tests-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        server.DATA_FILE = self.root / "web_state.json"
        server.TIMER_FILE = self.root / "timer_checkpoint.json"
        server.STATIC_DIR = ROOT / "web/static"
        server.DEFAULT_STATE = copy.deepcopy(DEFAULTS)
        server.DEFAULT_STATE["showBootWifiInfo"] = False
        server.settings_sessions = server.SettingsSessions()
        self.audio = patch.object(server, "apply_audio_output_mode", return_value=True)
        self.volume = patch.object(server, "set_system_volume_percent", return_value=True)
        self.default_sink = patch.object(server, "current_audio_sink", return_value="")
        self.audio_mock = self.audio.start()
        self.volume_mock = self.volume.start()
        self.default_sink.start()
        self.addCleanup(self.audio.stop)
        self.addCleanup(self.volume.stop)
        self.addCleanup(self.default_sink.stop)
        server.store = self.s = server.Store()
        server.results_store = self.db = server.ResultsStore(self.root / "results.sqlite3")
        self.addCleanup(self.stop_backup_retry)

    def stop_backup_retry(self):
        if self.db.backup_retry:
            self.db.backup_retry.cancel()

    @contextmanager
    def http_server(self):
        httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self.port = httpd.server_port
        try:
            yield
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(3)

    def request(self, path, payload=None, token="", raw=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        headers = {"Authorization": "Bearer " + token} if token else {}
        body = raw if raw is not None else json.dumps(payload) if payload is not None else None
        if body is not None:
            headers["Content-Type"] = "application/json"
        conn.request("POST" if body is not None else "GET", path, body=body, headers=headers)
        response = conn.getresponse()
        status = response.status
        content = response.read()
        conn.close()
        try:
            return status, json.loads(content)
        except (ValueError, UnicodeError):
            return status, content

    def settings(self, **values):
        return self.s.action({"action": "update_settings", **values}, settings_authorized=True)

    def music_library(self):
        music_root = self.root / "music"
        music_root.mkdir(exist_ok=True)
        external = patch.object(server, "EXTERNAL_MUSIC_DIRS", [])
        project = patch.object(server, "PROJECT_MUSIC_DIR", music_root)
        external.start()
        project.start()
        self.addCleanup(external.stop)
        self.addCleanup(project.stop)
        server.MUSIC_TRACKS_CACHE.update(timestamp=0, tracks=[])
        return music_root

    def add_music(self, relative_path):
        path = self.music_library_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fake music")
        server.MUSIC_TRACKS_CACHE.update(timestamp=0, tracks=[])
        return path

    def music_action(self, action, **values):
        return self.s.action({"action": action,
                              "trackId": self.s.state["selectedMusicTrack"],
                              "musicPlaybackEpoch": self.s.state["musicPlaybackEpoch"],
                              **values})

    def test_sequence_stays_in_selected_directory_and_resumes_after_reboot(self):
        self.music_library_root = self.music_library()
        for name in ("album/01.mp3", "album/02.mp3", "album/03.mp3", "other/99.mp3"):
            self.add_music(name)
        selection = "dir:project:album"
        result = self.settings(musicEnabled=True, selectedMusicItem=selection, musicMode="sequence")
        self.assertTrue(result["ok"])
        self.assertEqual(self.s.state["selectedMusicTrack"], "project:album/01.mp3")
        self.s.state["musicPlaying"] = True
        self.assertTrue(self.music_action("music_track_ended")["ok"])
        self.assertEqual(self.s.state["selectedMusicTrack"], "project:album/02.mp3")
        self.assertTrue(self.music_action("music_track_ended")["ok"])
        self.assertEqual(self.s.state["selectedMusicTrack"], "project:album/03.mp3")
        self.assertTrue(self.music_action("music_progress", positionSeconds=37.5)["ok"])
        self.settings(selectedMusicItem=selection, musicMode="sequence", musicVolumePercent=62)
        self.assertEqual(self.s.state["selectedMusicTrack"], "project:album/03.mp3")
        self.assertEqual(self.s.state["musicPositionSeconds"], 37.5)
        resumed = server.Store()
        self.assertEqual(resumed.state["selectedMusicItem"], selection)
        self.assertEqual(resumed.state["selectedMusicTrack"], "project:album/03.mp3")
        self.assertEqual(resumed.state["musicPositionSeconds"], 37.5)
        resumed.state["musicPlaying"] = True
        self.assertTrue(resumed.action({"action": "music_track_ended", "trackId": "project:album/03.mp3",
                                        "musicPlaybackEpoch": resumed.state["musicPlaybackEpoch"]})["ok"])
        self.assertEqual(resumed.state["selectedMusicTrack"], "project:album/01.mp3")

    def test_random_cycle_persists_and_rejects_stale_progress_and_ended(self):
        self.music_library_root = self.music_library()
        for name in ("01.mp3", "02.mp3", "03.mp3", "04.mp3"):
            self.add_music(name)
        self.settings(musicEnabled=True, selectedMusicItem="dir:project:.", musicMode="random")
        self.s.state["musicPlaying"] = True
        first_queue = list(self.s.state["musicShuffleQueue"])
        self.assertEqual(len(first_queue), 4)
        stale = {"trackId": self.s.state["selectedMusicTrack"],
                 "musicPlaybackEpoch": self.s.state["musicPlaybackEpoch"]}
        self.assertTrue(self.music_action("music_track_ended")["ok"])
        self.assertFalse(self.s.action({"action": "music_track_ended", **stale})["ok"])
        self.assertFalse(self.s.action({"action": "music_progress", **stale,
                                        "positionSeconds": 99})["ok"])
        self.assertEqual(self.s.state["musicPositionSeconds"], 0)
        self.assertEqual(self.s.state["musicShuffleIndex"], 1)
        resumed = server.Store()
        self.assertEqual(resumed.state["musicShuffleQueue"], first_queue)
        self.assertEqual(resumed.state["musicShuffleIndex"], 1)
        resumed.state["musicPlaying"] = True
        played = first_queue[:2]
        for _ in range(2):
            current = resumed.state["selectedMusicTrack"]
            self.assertTrue(resumed.action({"action": "music_track_ended", "trackId": current,
                                            "musicPlaybackEpoch": resumed.state["musicPlaybackEpoch"]})["ok"])
            played.append(resumed.state["selectedMusicTrack"])
        self.assertEqual(set(played), set(first_queue))
        last = resumed.state["selectedMusicTrack"]
        self.assertTrue(resumed.action({"action": "music_track_ended", "trackId": last,
                                        "musicPlaybackEpoch": resumed.state["musicPlaybackEpoch"]})["ok"])
        self.assertNotEqual(resumed.state["selectedMusicTrack"], last)
        self.assertEqual(resumed.state["musicShuffleIndex"], 0)

    def test_track_selection_uses_its_parent_directory_and_legacy_state_migrates(self):
        self.music_library_root = self.music_library()
        for name in ("album/01.mp3", "album/02.mp3", "other/01.mp3"):
            self.add_music(name)
        track = "project:album/02.mp3"
        self.settings(musicEnabled=True, selectedMusicItem=track, musicMode="sequence")
        self.assertEqual(self.s.state["selectedMusicTrack"], track)
        self.s.state["musicPlaying"] = True
        self.music_action("music_track_ended")
        self.assertEqual(self.s.state["selectedMusicTrack"], "project:album/01.mp3")
        self.s.state.pop("selectedMusicItem")
        self.s.state["selectedMusicTrack"] = track
        self.s.save()
        migrated = server.Store()
        self.assertEqual(migrated.state["selectedMusicItem"], track)
        self.assertEqual(migrated.state["selectedMusicTrack"], track)

    def test_loop_replay_epoch_rejects_delayed_progress(self):
        self.music_library_root = self.music_library()
        self.add_music("one.mp3")
        self.settings(musicEnabled=True, selectedMusicItem="project:one.mp3", musicMode="loop")
        self.s.state["musicPlaying"] = True
        old = {"trackId": self.s.state["selectedMusicTrack"],
               "musicPlaybackEpoch": self.s.state["musicPlaybackEpoch"]}
        self.assertTrue(self.s.action({"action": "music_track_ended", **old})["ok"])
        self.assertEqual(self.s.state["selectedMusicTrack"], old["trackId"])
        self.assertFalse(self.s.action({"action": "music_progress", **old,
                                        "positionSeconds": 100})["ok"])
        self.assertFalse(self.s.action({"action": "music_track_ended", **old})["ok"])
        self.assertEqual(self.s.state["musicPositionSeconds"], 0)

    def test_music_file_supports_range_requests_for_saved_position(self):
        self.music_library_root = self.music_library()
        track = self.add_music("seek.mp3")
        track.write_bytes(b"0123456789")
        with self.http_server():
            for range_header, expected_status, expected_body, expected_range in (
                ("bytes=4-7", 206, b"4567", "bytes 4-7/10"),
                ("bytes=8-", 206, b"89", "bytes 8-9/10"),
                ("bytes=-3", 206, b"789", "bytes 7-9/10"),
                ("bytes=20-", 416, b"", "bytes */10"),
            ):
                conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
                conn.request("GET", "/api/music/file?id=project%3Aseek.mp3", headers={"Range": range_header})
                response = conn.getresponse()
                self.assertEqual(response.status, expected_status)
                self.assertEqual(response.getheader("Content-Range"), expected_range)
                self.assertEqual(response.read(), expected_body)
                conn.close()

    def count_matches(self):
        with self.db.connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]

    def test_public_and_historical_state_exclude_passwords(self):
        state = self.s.snapshot()
        for name in ("finishPassword", "settingsPassword", "hotspotPassword"):
            self.assertNotIn(name, state)
        self.assertEqual(state["settingsPasswordLength"], 4)
        self.assertEqual(state["finishPasswordLength"], 4)
        state["legacy"] = {"settingsPassword": "old-secret"}
        match_id = self.db.save_match(state)
        # Simulate an existing pre-migration snapshot containing private fields.
        with self.db.connection() as conn:
            conn.execute("UPDATE matches SET snapshot_json = ? WHERE id = ?",
                         (json.dumps({"finishPassword": "old-secret", "redTotal": 3}), match_id))
        detail = self.db.match_detail(match_id)
        self.assertNotIn("old-secret", json.dumps(detail))

    def test_settings_login_once_save_many_change_password_and_logout(self):
        with self.http_server():
            _, wrong = self.request("/api/settings/login", {"password": "wrong"})
            self.assertFalse(wrong["ok"])
            self.assertNotIn("token", wrong)
            _, login = self.request("/api/settings/login", {"password": "1234"})
            token = login["token"]
            _, other = self.request("/api/settings/login", {"password": "1234"})
            self.assertIn("hotspotPassword", login["settings"])
            for values in ({"voiceProfile": "male"}, {"allowScoringWhenPaused": True},
                           {"settingsPassword": "12", "finishPassword": "678901"},
                           {"titleColor": "#123456"}):
                _, result = self.request("/api/action", {"action": "update_settings", **values}, token)
                self.assertTrue(result["ok"], result)
                self.assertNotIn("settingsPassword", result["state"])
            self.assertEqual(self.request("/api/settings/session", token=token)[0], 200)
            self.assertEqual(self.request("/api/settings/session", token=other["token"])[0], 401)
            self.assertEqual(self.s.snapshot()["settingsPasswordLength"], 2)
            self.assertEqual(self.s.snapshot()["finishPasswordLength"], 6)
            self.request("/api/settings/logout", {}, token)
            _, denied = self.request("/api/action", {"action": "update_settings", "voiceProfile": "female"}, token)
            self.assertTrue(denied["requiresSettingsLogin"])
            self.assertFalse(self.request("/api/settings/login", {"password": "1234"})[1]["ok"])
            self.assertTrue(self.request("/api/settings/login", {"password": "12"})[1]["ok"])

    def test_preview_clears_only_for_authorized_request_or_logout(self):
        with self.http_server():
            token = self.request("/api/settings/login", {"password": "1234"})[1]["token"]
            self.assertTrue(self.request("/api/action", {"action": "preview_title_style",
                                                     "titleColor": "#123456"}, token)[1]["ok"])
            self.assertEqual(self.s.snapshot()["titleColor"], "#123456")
            denied = self.request("/api/action", {"action": "clear_appearance_preview"})[1]
            self.assertTrue(denied["requiresSettingsLogin"])
            self.request("/api/settings/logout", {}, "invalid")
            self.assertEqual(self.s.snapshot()["titleColor"], "#123456")
            self.request("/api/settings/logout", {}, token)
            self.assertEqual(self.s.snapshot()["titleColor"], self.s.state["titleColor"])

    def test_preview_expires_without_extending_settings_session(self):
        with self.http_server():
            token = self.request("/api/settings/login", {"password": "1234"})[1]["token"]
            self.request("/api/action", {"action": "preview_title_style", "titleColor": "#123456"}, token)
            session_expiry = server.settings_sessions.tokens[token]
            self.assertEqual(self.s.snapshot()["titleColor"], "#123456")
            self.assertEqual(server.settings_sessions.tokens[token], session_expiry)
            self.s.preview_expires_at = server.time.monotonic() - 1
            self.assertEqual(self.s.snapshot()["titleColor"], self.s.state["titleColor"])
            self.request("/api/action", {"action": "preview_title_style", "titleColor": "#654321"}, token)
            server.settings_sessions.tokens[token] = server.time.monotonic() - 1
            self.assertEqual(self.s.snapshot()["titleColor"], self.s.state["titleColor"])
            self.assertFalse(self.s.preview_state)

    def test_other_settings_session_cannot_clear_active_preview(self):
        with self.http_server():
            first = self.request("/api/settings/login", {"password": "1234"})[1]["token"]
            second = self.request("/api/settings/login", {"password": "1234"})[1]["token"]
            self.request("/api/action", {"action": "preview_title_style", "titleColor": "#111111"}, first)
            self.request("/api/action", {"action": "preview_title_style", "titleColor": "#222222"}, second)
            self.assertEqual(self.s.snapshot()["titleColor"], "#222222")
            self.request("/api/action", {"action": "update_settings", "voiceProfile": "male"}, first)
            self.assertEqual(self.s.snapshot()["titleColor"], "#222222")
            self.request("/api/settings/logout", {}, first)
            self.assertEqual(self.s.snapshot()["titleColor"], "#222222")
            self.request("/api/settings/logout", {}, second)
            self.assertEqual(self.s.snapshot()["titleColor"], self.s.state["titleColor"])

    def test_saved_volume_restored_at_boot_and_default_sink_passed_to_device_job(self):
        self.volume_mock.assert_called_with(100)
        self.s.state["defaultAudioSink"] = "original-sink"
        self.assertTrue(self.settings(audioOutputMode="default")["ok"])
        self.s.device_jobs.queue.join()
        self.audio_mock.assert_any_call("default", "original-sink")
        self.volume_mock.assert_called_with(100)

    def test_default_audio_mode_restores_recorded_sink(self):
        calls = []
        def run(command, **kwargs):
            calls.append((command, kwargs))
            return types.SimpleNamespace(returncode=0, stdout="")
        with patch.object(server, "available_pactl_sinks", return_value=["original-sink", "hdmi-sink"]), \
                patch.object(server.subprocess, "run", side_effect=run):
            self.assertTrue(APPLY_AUDIO_OUTPUT_MODE("default", "original-sink"))
            self.assertFalse(APPLY_AUDIO_OUTPUT_MODE("default", "missing-sink"))
        self.assertIn(["pactl", "set-default-sink", "original-sink"], [command for command, _ in calls])
        self.assertTrue(all("env" in kwargs for _, kwargs in calls))

    def test_system_volume_uses_audio_session_environment(self):
        calls = []
        def run(command, **kwargs):
            calls.append((command, kwargs))
            return types.SimpleNamespace(returncode=1 if command[0] == "wpctl" else 0)
        with patch.object(server.subprocess, "run", side_effect=run):
            self.assertTrue(SET_SYSTEM_VOLUME_PERCENT(42))
        self.assertIn(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "42%"], [command for command, _ in calls])
        self.assertTrue(all("env" in kwargs for _, kwargs in calls))

    def test_all_settings_actions_require_session_not_raw_password(self):
        before = copy.deepcopy(self.s.state)
        for action in server.SETTINGS_ACTIONS | {"simulate_rf_signal"}:
            result = self.s.action({"action": action, "password": "1234"})
            self.assertTrue(result.get("requiresSettingsLogin"), action)
        self.assertEqual(before, self.s.state)
        with self.http_server(), patch.object(server, "connect_wifi") as connect:
            self.assertEqual(self.request("/api/network/connect", {"ssid": "test", "password": "test"})[0], 401)
            connect.assert_not_called()

    def test_paused_settings_preserve_progress_even_if_duration_changes(self):
        now = [10000.0]
        with patch.object(server.time, "monotonic", side_effect=lambda: now[0]):
            self.s.action({"action": "toggle_timer"})
            now[0] += 600
            self.s.action({"action": "toggle_timer"})
            self.assertEqual(self.s.state["remainingSeconds"], 1200)
            self.assertTrue(self.settings(durationMinutes="30", voiceProfile="male")["ok"])
            self.assertEqual(self.s.state["remainingSeconds"], 1200)
            self.settings(durationMinutes="45")
            self.assertEqual(self.s.state["remainingSeconds"], 1200)
            self.assertEqual(self.s.state["durationSeconds"], 2700)

    def test_pause_precision_and_wall_clock_jump(self):
        now = [10000.0]
        with patch.object(server.time, "monotonic", side_effect=lambda: now[0]):
            for _ in range(10):
                self.s.action({"action": "toggle_timer"})
                now[0] += .1
                self.s.action({"action": "toggle_timer"})
            self.assertAlmostEqual(self.s.state["remainingPreciseSeconds"], 1799, places=6)
            self.s.action({"action": "toggle_timer"})
            with patch.object(server.time, "time", return_value=9999999999):
                state = self.s.snapshot()
            self.assertFalse(state["timeExpired"])
            self.assertGreaterEqual(state["remainingSeconds"], 1799)

    def test_power_loss_restores_scores_and_checkpoint_paused_without_password(self):
        now = [10000.0]
        with patch.object(server.time, "monotonic", side_effect=lambda: now[0]):
            self.s.action({"action": "toggle_timer"})
            self.s.action({"action": "select", "ball": 3})
            self.s.action({"action": "advance"})
            now[0] += 123.4
            self.s.tick()
            uid = self.s.state["matchId"]
            self.assertLess(server.TIMER_FILE.stat().st_size, 256)
            # Reboot after arbitrary downtime, with unrelated monotonic epoch.
            now[0] = 1.0
            resumed = server.Store()
            state = resumed.snapshot()
            self.assertEqual(state["redTotal"], 1)
            self.assertEqual(state["matchId"], uid)
            self.assertFalse(state["running"])
            self.assertTrue(state["timerStarted"])
            self.assertAlmostEqual(state["remainingPreciseSeconds"], 1676.6, places=5)
            self.assertTrue(resumed.action({"action": "toggle_timer"})["ok"])
            now[0] += 10
            self.assertAlmostEqual(resumed.snapshot()["remainingPreciseSeconds"], 1666.6, places=5)
            resumed.action({"action": "select", "ball": 3})
            self.assertEqual(resumed.action({"action": "undo"})["state"]["redTotal"], 0)

    def test_paused_save_supersedes_older_checkpoint(self):
        now = [10000.0]
        with patch.object(server.time, "monotonic", side_effect=lambda: now[0]):
            self.s.action({"action": "toggle_timer"})
            now[0] += 100
            self.s.tick()
            now[0] += .5
            self.s.action({"action": "toggle_timer"})
            resumed = server.Store()
            self.assertAlmostEqual(resumed.state["remainingPreciseSeconds"], 1699.5)

    def test_old_state_without_precise_time_restores_existing_remaining(self):
        self.s.state.update(timerStarted=True, remainingSeconds=900)
        self.s.state.pop("remainingPreciseSeconds")
        self.s.save()
        resumed = server.Store()
        self.assertEqual(resumed.state["remainingPreciseSeconds"], 900)
        self.assertEqual(resumed.state["remainingSeconds"], 900)

    def test_finished_match_restarts_as_next_match_without_duplicate_result(self):
        uid = self.s.state["matchId"]
        self.s.action({"action": "finish", "password": "9999"})
        resumed = server.Store()
        self.assertEqual(self.count_matches(), 1)
        self.assertEqual(resumed.state["matchNumber"], 2)
        self.assertNotEqual(resumed.state["matchId"], uid)
        self.assertFalse(resumed.state["timerStarted"])

    def test_rf_waits_for_finish_transaction(self):
        self.s.state.update(allowScoringWhenPaused=True, selectedBallAt=server.time.time())
        self.s.state["rfRemoteSlots"][0].update(enabled=True, bindings={"advance": {"raw": "abc"}})
        started = threading.Event()
        done = threading.Event()
        def rf():
            started.set()
            self.s.action({"action": "simulate_rf_signal", "raw": "abc"}, internal=True)
            done.set()
        worker = threading.Thread(target=rf, daemon=True)
        with self.s.lock:
            worker.start()
            self.assertTrue(started.wait(1))
            self.assertFalse(done.wait(.05))
            self.s.action({"action": "finish", "password": "9999"})
        worker.join(2)
        self.assertTrue(done.is_set())
        self.assertEqual(self.s.snapshot()["redTotal"], 0)
        self.assertEqual(self.db.match_detail(1)["match"]["red_score"], 0)

    def test_rf_remote_uses_only_assigned_receiver_and_deduplicates_sources(self):
        receivers = [
            {"id": "rx1", "name": "UART 1", "enabled": True, "type": "serial", "serialDevice": "/dev/ttyS1"},
            {"id": "rx2", "name": "UART 2", "enabled": True, "type": "serial", "serialDevice": "/dev/ttyUSB0"},
        ]
        self.assertTrue(self.s.action({"action": "update_rf_settings", "rfReceivers": receivers}, settings_authorized=True)["ok"])
        self.assertTrue(self.s.action({
            "action": "update_rf_remote_slot", "slotId": "rf1", "name": "遥控器1", "enabled": True,
            "receiverIds": ["rx2"], "bindings": {"toggle_timer": {"raw": "code-1"}},
        }, settings_authorized=True)["ok"])
        ignored = self.s.action({"action": "simulate_rf_signal", "raw": "code-1", "receiverId": "rx1"}, internal=True)
        self.assertFalse(ignored["ok"])
        self.assertFalse(self.s.state["running"])
        accepted = self.s.action({"action": "simulate_rf_signal", "raw": "code-1", "receiverId": "rx2"}, internal=True)
        self.assertTrue(accepted["ok"])
        self.assertTrue(self.s.state["running"])

        self.s.state["rfRemoteSlots"][0]["receiverIds"] = ["rx1", "rx2"]
        self.s.last_rf_signal_by_raw.clear()
        self.s.action({"action": "simulate_rf_signal", "raw": "code-1", "receiverId": "rx1"}, internal=True)
        running_after_first = self.s.state["running"]
        duplicate = self.s.action({"action": "simulate_rf_signal", "raw": "code-1", "receiverId": "rx2"}, internal=True)
        self.assertEqual(duplicate["message"], "duplicate")
        self.assertEqual(self.s.state["running"], running_after_first)

    def test_serial_device_history_preserves_long_by_id_path(self):
        stable = "/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0"
        for device in (stable, "/dev/ttyS1"):
            result = self.s.action({
                "action": "update_rf_settings",
                "rfReceivers": [{"id": "rx1", "name": "ESP32", "enabled": True, "type": "serial", "serialDevice": device}],
            }, settings_authorized=True)
            self.assertTrue(result["ok"])
        self.assertIn(stable, self.s.state["rfSerialDeviceHistory"])
        self.assertIn("/dev/ttyS1", self.s.snapshot()["rfSerialDevices"])

    def test_legacy_single_receiver_migrates_without_losing_serial_path(self):
        self.s.state.pop("rfReceivers", None)
        self.s.state.update(rfReceiverType="serial", rfReceiverSerialDevice="/dev/ttyS1", rfReceiverGpio=18)
        self.s.save()
        resumed = server.Store()
        self.assertEqual(resumed.state["rfReceivers"][0]["type"], "serial")
        self.assertEqual(resumed.state["rfReceivers"][0]["serialDevice"], "/dev/ttyS1")
        self.assertEqual(resumed.state["rfRemoteSlots"][0]["receiverIds"], ["rx1"])

    def test_backup_failure_does_not_fail_finish_or_duplicate_result(self):
        with patch.object(self.db, "backup_after_match", side_effect=OSError("test failure")), self.assertLogs(level="ERROR"):
            response = self.s.action({"action": "finish", "password": "9999"})
        self.assertTrue(response["ok"])
        self.assertTrue(response["state"]["matchFinished"])
        self.assertEqual(self.count_matches(), 1)
        self.s.action({"action": "finish", "password": "9999"})
        self.db.save_match(response["finishedMatch"])
        self.assertEqual(self.count_matches(), 1)

    def test_migration_adds_uid_to_existing_database(self):
        legacy = self.root / "legacy.sqlite3"
        with sqlite3.connect(legacy) as conn:
            conn.execute("""CREATE TABLE matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT, match_number INTEGER NOT NULL,
                title TEXT NOT NULL, match_date TEXT NOT NULL, started_at TEXT,
                ended_at TEXT NOT NULL, red_team TEXT NOT NULL, red_score INTEGER NOT NULL,
                white_score INTEGER NOT NULL, white_team TEXT NOT NULL, balls_json TEXT NOT NULL,
                snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL)""")
        conn.close()
        migrated = server.ResultsStore(legacy)
        snapshot = self.s.snapshot()
        first = migrated.save_match(snapshot)
        self.assertEqual(first, migrated.save_match(snapshot))
        with migrated.connection() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0], 1)

    def test_bad_requests_leave_server_and_settings_usable(self):
        with self.http_server():
            for body in ("{", "[]", "null", "x" * 65537):
                self.assertEqual(self.request("/api/action", raw=body)[0], 400)
            self.assertEqual(self.request("/api/results/month?year=abc")[0], 400)
            self.assertEqual(self.request("/api/results/month?month=99")[0], 400)
            self.assertEqual(self.request("/api/state")[0], 200)
        before = self.s.state["voiceProfile"]
        result = self.settings(durationMinutes="bad", voiceProfile="male")
        self.assertFalse(result["ok"])
        self.assertEqual(self.s.state["voiceProfile"], before)

    def test_prefixed_serial_json_matches_plain_json(self):
        payload = json.dumps({"raw": "0x57F0FF", "bits": 24})
        parsed = server.rf_payload_from_serial_line(payload)
        self.assertIsNotNone(parsed)
        self.assertEqual(server.rf_payload_from_serial_line("RFJSON: " + payload), parsed)
        self.assertIsNone(server.rf_payload_from_serial_line('RFJSON: {"raw":"0x57F0FF","bits":32}'))

    def test_static_paths_cannot_escape(self):
        static = self.root / "web/static"
        static.mkdir(parents=True)
        (static / "allowed.txt").write_text("allowed")
        (self.root / "secret.txt").write_text("private-test-data")
        server.STATIC_DIR = static
        with self.http_server():
            for path in ("/../../secret.txt", "/%2e%2e/%2e%2e/secret.txt", "/..%5c..%5csecret.txt"):
                status, content = self.request(path)
                self.assertEqual(status, 404, path)
                self.assertNotIn(b"private-test-data", content)
            self.assertEqual(self.request("/allowed.txt"), (200, b"allowed"))

    def test_device_settings_do_not_block_match_actions(self):
        entered, release = threading.Event(), threading.Event()
        def configure(*args):
            entered.set()
            self.assertTrue(release.wait(3))
            return {"ok": True, "supported": True}
        with patch.object(server, "configure_hotspot", side_effect=configure):
            try:
                result = self.settings(hotspotSsid="test-hotspot")
                self.assertTrue(result["ok"])
                self.assertTrue(entered.wait(1))
                self.assertEqual(self.s.action({"action": "select", "ball": 2})["state"]["selectedBall"], 2)
            finally:
                release.set()
                self.s.device_jobs.queue.join()
        self.assertEqual(self.s.state["deviceSettingsStatus"]["status"], "done")

    def test_failed_device_settings_can_retry_same_saved_values(self):
        with patch.object(server, "configure_hotspot", return_value={"ok": False}):
            self.settings(hotspotSsid="test-hotspot")
            self.s.device_jobs.queue.join()
        self.assertEqual(self.s.state["deviceSettingsStatus"]["status"], "error")
        with patch.object(server, "configure_hotspot", return_value={"ok": True, "supported": True}) as configure:
            self.settings(hotspotSsid="test-hotspot")
            self.s.device_jobs.queue.join()
            configure.assert_called_once()
        self.assertEqual(self.s.state["deviceSettingsStatus"]["status"], "done")


if __name__ == "__main__":
    unittest.main()
