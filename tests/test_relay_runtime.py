import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pmbridge import cli, relay_runtime


class RelayRuntimeTests(unittest.TestCase):
    def test_keychain_lookup_uses_security_without_returning_command_output(self):
        calls = []

        def run(command, **kwargs):
            calls.append((command, kwargs))
            return relay_runtime.Completed(returncode=0, stdout="secret-value\n", stderr="")

        store = relay_runtime.KeychainStore(account="tester", runner=run)

        self.assertEqual(store.get("control-plane"), "secret-value")
        self.assertEqual(calls[0][0][:4], ["/usr/bin/security", "find-generic-password", "-a", "tester"])

    def test_status_redacts_credentials_and_reports_keychain_presence(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / ".pmbridge"
            runtime = relay_runtime.RelayRuntime(
                home,
                relay_runtime.RelayConfig(
                    home=home,
                    relay_command=["/bin/relay"],
                    tunnel_command=["/bin/tunnel"],
                    relay_host="127.0.0.1",
                    relay_port=18788,
                ),
                keychain=relay_runtime.MemoryKeychain({"control-plane": "api-secret", "relay-auth": "bearer-secret"}),
            )

            result = runtime.status()
            encoded = json.dumps(result)

            self.assertEqual(result["status"], "STOPPED")
            self.assertTrue(result["credentials"]["control_plane_api_key_present"])
            self.assertTrue(result["credentials"]["desktop_relay_auth_present"])
            self.assertNotIn("api-secret", encoded)
            self.assertNotIn("bearer-secret", encoded)

    @patch("pmbridge.relay_runtime.subprocess.Popen")
    def test_start_is_idempotent_when_supervisor_is_alive(self, popen):
        import os

        popen.return_value.pid = os.getpid()
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / ".pmbridge"
            runtime = relay_runtime.RelayRuntime(
                home,
                relay_runtime.RelayConfig(home=home, relay_command=["/bin/relay"], tunnel_command=["/bin/tunnel"]),
                keychain=relay_runtime.MemoryKeychain({"control-plane": "api-secret", "relay-auth": "bearer-secret"}),
            )
            first = runtime.start()
            second = runtime.start()

            self.assertEqual(first["status"], "STARTED")
            self.assertEqual(second["status"], "ALREADY_RUNNING")
            self.assertEqual(popen.call_count, 1)

    def test_cli_exposes_relay_operator_surface(self):
        args = cli.build_parser().parse_args(["relay", "autostart", "status", "--json"])
        self.assertEqual(args.command, "relay")
        self.assertEqual(args.relay_command, "autostart")
        self.assertEqual(args.autostart_command, "status")

    def test_configure_copies_profile_and_replaces_file_key_with_environment_reference(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source_config = root / "spike-config.json"
            source_config.write_text(json.dumps({
                "listenHost": "127.0.0.1",
                "listenPort": 18788,
                "upstreamCmd": ["/node", "unused"],
            }), encoding="utf-8")
            source_profiles = root / "profiles"
            source_profiles.mkdir()
            (source_profiles / "relay-http.yaml").write_text(
                'control_plane:\n  tunnel_id: "tunnel_test"\n  api_key: "file:/secret/key"\n'
                'mcp:\n  extra_headers:\n    Authorization: "env:DESKTOP_RELAY_AUTH"\n',
                encoding="utf-8",
            )
            home = root / ".pmbridge"

            result = relay_runtime.configure_from_source(
                home, source_config, root / "tunnel-client", "relay-http", source_profiles,
            )
            generated = home / "relay" / "profiles" / "relay-http.yaml"

            self.assertEqual(result["status"], "READY")
            self.assertTrue(generated.exists())
            profile = generated.read_text(encoding="utf-8")
            self.assertIn('api_key: "env:CONTROL_PLANE_API_KEY"', profile)
            self.assertNotIn("file:/secret/key", profile)
            self.assertIn("env:DESKTOP_RELAY_AUTH", profile)
            saved = relay_runtime.RelayConfig.load(home / "relay" / "config.json")
            self.assertEqual(saved.relay_config_path, str(source_config.resolve()))


if __name__ == "__main__":
    unittest.main()
