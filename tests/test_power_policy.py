"""Exercise install/remove and reconnect hooks in a temporary tree with fake radios."""
from __future__ import annotations

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")
if not BASH and os.name == "nt":
    candidate = Path("C:/Program Files/Git/bin/bash.exe")
    BASH = str(candidate) if candidate.is_file() else None


@unittest.skipUnless(BASH, "Bash is required for deployment policy tests")
class PowerPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gateball-power-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "calls.log"
        self.paths = {name: self.root / name for name in (
            "NM_POWER_CONF", "NM_POWER_DISPATCHER", "SLEEP_POWER_CONF", "IDLE_POWER_CONF")}
        self.fake("nmcli", 'printf "nmcli %s\\n" "$*" >> "$POWER_TEST_LOG"\n')
        self.fake("iw", '''printf 'iw %s\\n' "$*" >> "$POWER_TEST_LOG"
case "$*" in
  dev) printf 'phy#0\\n\\tInterface wlan0\\n\\tInterface wlan0_ap\\n' ;;
  'dev wlan0 info'|'dev wlan0_ap info'|*' set power_save off') exit 0 ;;
  *) exit 1 ;;
esac
''')

    def fake(self, name, body):
        path = self.bin / name
        with path.open("w", encoding="utf-8", newline="\n") as output:
            output.write("#!/bin/bash\n" + body)
        path.chmod(0o755)

    def run_shell(self, command):
        script = ROOT / "deploy/raspberry-pi/configure-power.sh"
        setup = "\n".join([
            'export PATH="/usr/bin:/bin:$PATH"',
            "source " + shlex.quote(script.as_posix()),
            "POWER_TEST_BIN=" + shlex.quote(self.bin.as_posix()),
            'export PATH="$(cd "$POWER_TEST_BIN" && pwd):$PATH"',
            "export POWER_TEST_LOG=" + shlex.quote(self.log.as_posix()),
            *[name + "=" + shlex.quote(path.as_posix()) for name, path in self.paths.items()],
        ])
        result = subprocess.run([BASH, "-c", setup + "\n" + command],
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_install_repeat_and_remove_preserve_unrelated_files(self):
        other = self.root / "other.conf"
        other.write_text("unchanged")
        self.run_shell("install_power_policy\ninstall_power_policy")
        self.assertIn("wifi.powersave=2", self.paths["NM_POWER_CONF"].read_text())
        sleep = self.paths["SLEEP_POWER_CONF"].read_text()
        for key in ("AllowSuspend", "AllowHibernation", "AllowHybridSleep", "AllowSuspendThenHibernate"):
            self.assertIn(key + "=no", sleep)
        self.assertFalse(list(self.root.glob("*.gateball.bak")))
        calls = self.log.read_text()
        self.assertIn("iw dev wlan0 set power_save off", calls)
        self.assertIn("nmcli general reload conf", calls)
        self.assertNotIn("connection up", calls)
        self.run_shell("remove_power_policy\nremove_power_policy")
        for path in self.paths.values():
            self.assertFalse(path.exists())
        self.assertEqual(other.read_text(), "unchanged")

    def test_original_files_restored_after_repeated_install(self):
        for name, path in self.paths.items():
            path.write_text("original " + name)
        self.run_shell("install_power_policy\ninstall_power_policy\nremove_power_policy")
        for name, path in self.paths.items():
            self.assertEqual(path.read_text(), "original " + name)
        self.assertFalse(list(self.root.glob("*.gateball.bak")))

    def test_dispatcher_only_changes_wireless_up_or_reapply(self):
        self.run_shell("install_power_policy")
        self.log.write_text("")
        self.run_shell('bash "$NM_POWER_DISPATCHER" eth0 up\n'
                       'bash "$NM_POWER_DISPATCHER" wlan0 down\n'
                       'bash "$NM_POWER_DISPATCHER" wlan0 up\n'
                       'bash "$NM_POWER_DISPATCHER" wlan0 reapply')
        calls = self.log.read_text()
        self.assertEqual(calls.count("iw dev wlan0 set power_save off"), 2)
        self.assertNotIn("iw dev eth0 set power_save off", calls)
        self.assertNotIn("nmcli ", calls)

    def test_remove_keeps_replacement_not_owned_by_gateball(self):
        self.paths["NM_POWER_CONF"].write_text("original")
        self.run_shell("install_power_policy")
        self.paths["NM_POWER_CONF"].write_text("external replacement")
        self.run_shell("remove_power_policy")
        self.assertEqual(self.paths["NM_POWER_CONF"].read_text(), "external replacement")
        self.assertEqual(Path(str(self.paths["NM_POWER_CONF"]) + ".gateball.bak").read_text(), "original")


if __name__ == "__main__":
    unittest.main()
