import plistlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pmbridge import launchd, relay_runtime


class RelayLaunchdTests(unittest.TestCase):
    def test_relay_plist_is_loopback_safe_and_secret_free(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / ".pmbridge"
            config_path = home / "relay" / "config.json"
            text = launchd.render_relay_plist(home, config_path)
            payload = plistlib.loads(text.encode("utf-8"))

            self.assertEqual(payload["Label"], "com.pmbridge.relay")
            self.assertTrue(payload["RunAtLoad"])
            self.assertTrue(payload["KeepAlive"])
            self.assertEqual(payload["ProgramArguments"][0], str(home.resolve() / "bin" / "pmbridge"))
            self.assertIn("supervisor", payload["ProgramArguments"])
            self.assertNotIn("0.0.0.0", text)
            self.assertNotIn("CONTROL_PLANE_API_KEY", text)
            self.assertNotIn("DESKTOP_RELAY_AUTH", text)
            self.assertNotIn("sk-", text)

    @patch("pmbridge.launchd.subprocess.run")
    def test_relay_autostart_enable_uses_current_user_launch_agent(self, run):
        run.return_value.returncode = 0
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / ".pmbridge"
            config = relay_runtime.RelayConfig(home=home, relay_command=["/bin/relay"], tunnel_command=["/bin/tunnel"])
            config.save()
            destination = home / "LaunchAgents" / "com.pmbridge.relay.plist"

            result = launchd.relay_enable(home, destination=destination)

            self.assertEqual(result["status"], "ENABLED")
            self.assertEqual(run.call_count, 2)
            self.assertTrue(any("bootstrap" in call.args[0] for call in run.call_args_list))
            self.assertTrue(destination.exists())

    @patch("pmbridge.launchd.subprocess.run")
    def test_relay_autostart_disable_unloads_only_relay_label(self, run):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / ".pmbridge"
            destination = home / "LaunchAgents" / "com.pmbridge.relay.plist"
            destination.parent.mkdir(parents=True)
            destination.write_text("plist")
            result = launchd.relay_disable(home, destination=destination)

            self.assertEqual(result["status"], "DISABLED")
            self.assertTrue(any("bootout" in call.args[0] for call in run.call_args_list))
            self.assertTrue(all("com.pmbridge.relay" in call.args[0][-1] or "com.pmbridge.relay" in str(call.args[0]) for call in run.call_args_list))
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
