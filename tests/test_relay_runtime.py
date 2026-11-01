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

    @patch("pmbridge.relay_runtime.launchd.relay_enable")
    def test_start_uses_launchd_as_the_only_supervisor_owner(self, enable):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / ".pmbridge"
            runtime = relay_runtime.RelayRuntime(
                home,
                relay_runtime.RelayConfig(home=home, relay_command=["/bin/relay"], tunnel_command=["/bin/tunnel"]),
                keychain=relay_runtime.MemoryKeychain({"control-plane": "api-secret", "relay-auth": "bearer-secret"}),
            )
            enable.return_value = {"status": "ENABLED", "label": "com.pmbridge.relay"}
            with patch.object(runtime, "_owned_processes", return_value=[]), patch.object(runtime, "_wait_for_ready", return_value=True):
                first = runtime.start()

            self.assertEqual(first["status"], "READY")
            enable.assert_called_once_with(home.resolve())

    @patch("pmbridge.relay_runtime.launchd.relay_enable")
    @patch("pmbridge.relay_runtime.launchd.relay_disable")
    def test_restart_unloads_then_loads_the_single_launchd_owner(self, disable, enable):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / ".pmbridge"
            runtime = relay_runtime.RelayRuntime(
                home,
                relay_runtime.RelayConfig(home=home, relay_command=["/bin/relay"], tunnel_command=["/bin/tunnel"]),
                keychain=relay_runtime.MemoryKeychain({"control-plane": "api-secret", "relay-auth": "bearer-secret"}),
            )
            disable.return_value = {"status": "DISABLED", "label": "com.pmbridge.relay"}
            enable.return_value = {"status": "ENABLED", "label": "com.pmbridge.relay"}
            with patch.object(runtime, "_terminate_owned_processes"), patch.object(runtime, "_wait_for_ready", return_value=True):
                result = runtime.restart()

            self.assertEqual(result["status"], "READY")
            disable.assert_called_once_with(home.resolve())
            enable.assert_called_once_with(home.resolve())

    @patch("pmbridge.relay_runtime.subprocess.run")
    def test_owned_process_snapshot_distinguishes_supervisor_data_plane_and_child(self, run):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / ".pmbridge"
            relay_root = Path(td) / "desktop-relay"
            daemon = relay_root / "src" / "daemon.ts"
            commander = relay_root / "node_modules/@wonderwhy-er/desktop-commander/dist/index.js"
            tunnel = Path(td) / "tunnel-client"
            runtime = relay_runtime.RelayRuntime(
                home,
                relay_runtime.RelayConfig(
                    home=home,
                    relay_command=["/node", str(daemon)],
                    tunnel_command=[str(tunnel), "run", "--profile-dir", str(home / "relay" / "profiles")],
                ),
                keychain=relay_runtime.MemoryKeychain(),
            )
            managed_home = runtime.home
            rows = "\n".join([
                f"101 1 python -m pmbridge.relay_runtime --supervise --home {managed_home}",
                f"102 101 /node {daemon}",
                f"103 101 {tunnel} run --profile-dir {managed_home / 'relay' / 'profiles'}",
                f"104 102 /node {commander}",
                "105 1 unrelated-process",
            ])
            run.return_value = relay_runtime.Completed(returncode=0, stdout=rows, stderr="")

            snapshot = runtime._owned_processes()

            self.assertEqual([(row["pid"], row["kind"]) for row in snapshot], [
                (101, "supervisor"), (102, "relay"), (103, "tunnel"), (104, "commander")
            ])

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
