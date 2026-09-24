"""Verify channel synchronization without touching the host network."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")
if not BASH and os.name == "nt":
    candidate = Path("C:/Program Files/Git/bin/bash.exe")
    BASH = str(candidate) if candidate.is_file() else None


@unittest.skipUnless(BASH, "Bash is required for network synchronization tests")
class NetworkSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gateball-network-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "calls.log"
        self.fake("iw", r'''
if [ "$1 $2 $3" = "dev wlan0 link" ]; then
  printf 'Connected to 00:11:22:33:44:55\n\tfreq: 2417\n'
elif [ "$1 $2 $3" = "dev wlan0_ap info" ]; then
  printf 'Interface wlan0_ap\n\tchannel %s (%s MHz), width: 20 MHz\n' "$FAKE_AP_CHANNEL" "$FAKE_AP_FREQUENCY"
fi
''')
        self.fake("nmcli", r'''
printf 'nmcli %s\n' "$*" >> "$NETWORK_TEST_LOG"
case "$*" in
  '-g GENERAL.CONNECTION device show wlan0') printf 'tsunami\n' ;;
  '-g 802-11-wireless.band connection show tsunami') printf 'bg\n' ;;
  '-g 802-11-wireless.bssid connection show tsunami') printf '%s\n' "${FAKE_BSSID:-}" ;;
  'connection show gateball-ap') exit 0 ;;
  '-g 802-11-wireless.channel connection show gateball-ap') printf '%s\n' "$FAKE_AP_CHANNEL" ;;
  '-t -f NAME connection show --active') printf 'tsunami\ngateball-ap\n' ;;
esac
''')

    def fake(self, name: str, body: str) -> None:
        path = self.bin / name
        path.write_text("#!/bin/bash\n" + body, encoding="utf-8", newline="\n")
        path.chmod(0o755)

    def run_sync(self, *, channel: int, frequency: int, bssid: str = "", recover: bool = False) -> str:
        env = os.environ.copy()
        env.update({
            "PATH": str(self.bin) + os.pathsep + env.get("PATH", ""),
            "NETWORK_TEST_LOG": str(self.log),
            "GATEBALL_NETWORK_SYNC_LOCK": str(self.root / "sync.lock"),
            "FAKE_AP_CHANNEL": str(channel),
            "FAKE_AP_FREQUENCY": str(frequency),
            "FAKE_BSSID": bssid,
        })
        command = [BASH, str(ROOT / "deploy/raspberry-pi/network-sync.sh")]
        if recover:
            command.append("--recover-uplink")
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return self.log.read_text(encoding="utf-8")

    def test_restarts_hotspot_only_when_channel_differs(self):
        calls = self.run_sync(channel=10, frequency=2457)
        self.assertIn("connection down gateball-ap", calls)
        self.assertIn("802-11-wireless.channel 2", calls)
        self.assertIn("connection up gateball-ap", calls)

    def test_matching_channel_does_not_restart_hotspot(self):
        calls = self.run_sync(channel=2, frequency=2417)
        self.assertNotIn("connection down gateball-ap", calls)
        self.assertNotIn("connection up gateball-ap", calls)

    def test_removes_saved_bssid_without_restarting_matching_hotspot(self):
        calls = self.run_sync(channel=2, frequency=2417, bssid="50:EB:F6:34:B7:88")
        self.assertIn("connection modify tsunami", calls)
        self.assertIn("802-11-wireless.bssid ", calls)
        self.assertNotIn("connection down gateball-ap", calls)

    def test_recovery_pauses_hotspot_before_reconnecting_uplink(self):
        calls = self.run_sync(channel=2, frequency=2417, recover=True)
        self.assertLess(calls.index("connection down gateball-ap"), calls.index("device connect wlan0"))


if __name__ == "__main__":
    unittest.main()
