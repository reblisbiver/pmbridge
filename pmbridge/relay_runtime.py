"""Lifecycle wrapper for the stock Desktop Relay and OpenAI tunnel-client."""

import getpass
import json
import os
import re
import shlex
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional


API_KEY_NAME = "control-plane"
RELAY_AUTH_NAME = "relay-auth"
KEYCHAIN_API_KEY_SERVICE = "pmbridge.control-plane-api-key"
KEYCHAIN_RELAY_AUTH_SERVICE = "pmbridge.desktop-relay-auth"
SUPERVISOR_PID_NAME = "supervisor.pid"
CHILDREN_STATE_NAME = "children.json"


@dataclass
class Completed:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class KeychainStore:
    def __init__(self, account: Optional[str] = None, runner: Callable = subprocess.run):
        self.account = account or getpass.getuser()
        self.runner = runner

    def get(self, name: str) -> Optional[str]:
        service = {
            API_KEY_NAME: KEYCHAIN_API_KEY_SERVICE,
            RELAY_AUTH_NAME: KEYCHAIN_RELAY_AUTH_SERVICE,
        }.get(name, name)
        result = self.runner(
            ["/usr/bin/security", "find-generic-password", "-a", self.account, "-s", service, "-w"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        value = (result.stdout or "").strip()
        return value or None


class MemoryKeychain:
    def __init__(self, values: Optional[Dict[str, str]] = None):
        self.values = dict(values or {})

    def get(self, name: str) -> Optional[str]:
        return self.values.get(name)


@dataclass
class RelayConfig:
    home: Path
    relay_command: List[str]
    tunnel_command: List[str]
    relay_host: str = "127.0.0.1"
    relay_port: int = 18788
    keychain_api_key: str = API_KEY_NAME
    keychain_relay_auth: str = RELAY_AUTH_NAME
    log_dir: Optional[Path] = None
    relay_config_path: Optional[str] = None

    def __post_init__(self):
        self.home = Path(self.home).expanduser().resolve()
        if self.log_dir is None:
            self.log_dir = self.home / "relay" / "logs"
        else:
            self.log_dir = Path(self.log_dir).expanduser().resolve()

    @property
    def path(self) -> Path:
        return self.home / "relay" / "config.json"

    def as_dict(self) -> dict:
        return {
            "version": 1,
            "relay_command": list(self.relay_command),
            "tunnel_command": list(self.tunnel_command),
            "relay_host": self.relay_host,
            "relay_port": self.relay_port,
            "keychain_api_key": self.keychain_api_key,
            "keychain_relay_auth": self.keychain_relay_auth,
            "log_dir": str(self.log_dir),
            "relay_config_path": self.relay_config_path,
        }

    def save(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.as_dict(), indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)
        return self.path

    @classmethod
    def load(cls, path: Path) -> "RelayConfig":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            home=Path(path).expanduser().resolve().parents[1],
            relay_command=list(payload["relay_command"]),
            tunnel_command=list(payload["tunnel_command"]),
            relay_host=payload.get("relay_host", "127.0.0.1"),
            relay_port=int(payload.get("relay_port", 18788)),
            keychain_api_key=payload.get("keychain_api_key", API_KEY_NAME),
            keychain_relay_auth=payload.get("keychain_relay_auth", RELAY_AUTH_NAME),
            log_dir=Path(payload["log_dir"]) if payload.get("log_dir") else None,
            relay_config_path=payload.get("relay_config_path"),
        )


def config_path(home: Path) -> Path:
    return Path(home).expanduser() / "relay" / "config.json"


def load_config(home: Path) -> Optional[RelayConfig]:
    path = config_path(home)
    if not path.is_file():
        return None
    return RelayConfig.load(path)


def configure_from_source(home: Path, source_config: Path, tunnel_binary: Path, profile: str, profile_dir: Path, health_addr: str = "127.0.0.1:18080") -> dict:
    source_path = Path(source_config).expanduser().resolve()
    source = json.loads(source_path.read_text(encoding="utf-8"))
    upstream = list(source["upstreamCmd"])
    if not upstream:
        raise ValueError("source relay config has no upstreamCmd")
    relay_root = source_path.parent
    relay_command = [upstream[0], str(relay_root / "src" / "daemon.ts")]
    profile_source = Path(profile_dir).expanduser().resolve() / f"{profile}.yaml"
    if not profile_source.is_file():
        raise ValueError(f"tunnel profile not found: {profile_source}")
    managed_profile_dir = Path(home).expanduser().resolve() / "relay" / "profiles"
    managed_profile_dir.mkdir(parents=True, exist_ok=True)
    managed_profile = managed_profile_dir / profile_source.name
    profile_text = profile_source.read_text(encoding="utf-8")
    profile_text = re.sub(
        r'(?m)^(\s*api_key:\s*)(?:"[^"]*"|[^\s#]+)\s*$',
        r'\1"env:CONTROL_PLANE_API_KEY"',
        profile_text,
    )
    managed_profile.write_text(profile_text, encoding="utf-8")
    os.chmod(managed_profile, 0o600)
    tunnel_command = [
        str(Path(tunnel_binary).expanduser().resolve()),
        "run",
        "--profile", profile,
        "--profile-dir", str(managed_profile_dir),
        "--health.listen-addr", health_addr,
    ]
    config = RelayConfig(
        home=home,
        relay_command=relay_command,
        tunnel_command=tunnel_command,
        relay_host=source.get("listenHost", "127.0.0.1"),
        relay_port=int(source.get("listenPort", 18788)),
        relay_config_path=str(source_path),
    )
    path = config.save()
    return {
        "status": "READY",
        "config": str(path),
        "relay_host": config.relay_host,
        "relay_port": config.relay_port,
        "profile": str(managed_profile),
        "relay_command": [shlex.quote(part) for part in relay_command],
        "tunnel_command": [shlex.quote(part) for part in tunnel_command],
    }


def _pid_alive(pid: Optional[int]) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError, ValueError):
        return False
    return True


class RelayRuntime:
    def __init__(self, home: Path, config: RelayConfig, keychain=None):
        self.home = Path(home).expanduser().resolve()
        self.config = config
        self.keychain = keychain or KeychainStore()
        self.relay_dir = self.home / "relay"
        self.pid_path = self.relay_dir / SUPERVISOR_PID_NAME
        self.children_path = self.relay_dir / CHILDREN_STATE_NAME

    def _read_pid(self) -> Optional[int]:
        try:
            return int(self.pid_path.read_text(encoding="utf-8").strip())
        except (FileNotFoundError, ValueError):
            return None

    def _read_children(self) -> dict:
        try:
            return json.loads(self.children_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError, json.JSONDecodeError):
            return {}

    def _credentials(self):
        return (
            self.keychain.get(self.config.keychain_api_key),
            self.keychain.get(self.config.keychain_relay_auth),
        )

    def status(self) -> dict:
        supervisor_pid = self._read_pid()
        children = self._read_children()
        supervisor_alive = _pid_alive(supervisor_pid)
        relay_pid = children.get("relay_pid")
        tunnel_pid = children.get("tunnel_pid")
        relay_alive = _pid_alive(relay_pid)
        tunnel_alive = _pid_alive(tunnel_pid)
        if supervisor_alive and relay_alive and tunnel_alive:
            state = "READY"
        elif supervisor_alive or relay_alive or tunnel_alive:
            state = "DEGRADED"
        else:
            state = "STOPPED"
        api_key, relay_auth = self._credentials()
        return {
            "status": state,
            "supervisor": {"pid": supervisor_pid, "running": supervisor_alive},
            "relay": {"pid": relay_pid, "running": relay_alive, "host": self.config.relay_host, "port": self.config.relay_port},
            "tunnel": {"pid": tunnel_pid, "running": tunnel_alive},
            "credentials": {
                "control_plane_api_key_present": bool(api_key),
                "desktop_relay_auth_present": bool(relay_auth),
            },
        }

    def doctor(self) -> dict:
        result = self.status()
        checks = [
            {"name": "config", "ok": bool(self.config.relay_command and self.config.tunnel_command)},
            {"name": "loopback", "ok": self.config.relay_host == "127.0.0.1"},
            {"name": "control_plane_api_key", "ok": result["credentials"]["control_plane_api_key_present"]},
            {"name": "desktop_relay_auth", "ok": result["credentials"]["desktop_relay_auth_present"]},
            {"name": "supervisor", "ok": result["supervisor"]["running"]},
            {"name": "relay", "ok": result["relay"]["running"]},
            {"name": "tunnel", "ok": result["tunnel"]["running"]},
        ]
        result["checks"] = checks
        result["status"] = "READY" if all(item["ok"] for item in checks) else "NOT_READY"
        return result

    def start(self) -> dict:
        current = self.status()
        if current["supervisor"]["running"]:
            return {**current, "status": "ALREADY_RUNNING"}
        api_key, relay_auth = self._credentials()
        missing = []
        if not api_key:
            missing.append("control-plane")
        if not relay_auth:
            missing.append("relay-auth")
        if missing:
            return {"status": "NOT_READY", "missing_credentials": missing}
        self.config.save()
        self.relay_dir.mkdir(parents=True, exist_ok=True)
        process = subprocess.Popen(
            [sys.executable, "-m", "pmbridge.relay_runtime", "--supervise", "--home", str(self.home)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self.pid_path.write_text(str(process.pid) + "\n", encoding="utf-8")
        return {"status": "STARTED", "supervisor_pid": process.pid}

    def stop(self) -> dict:
        pid = self._read_pid()
        if not _pid_alive(pid):
            self.pid_path.unlink(missing_ok=True)
            return {"status": "STOPPED", "already_stopped": True}
        os.kill(pid, signal.SIGTERM)
        self.pid_path.unlink(missing_ok=True)
        return {"status": "STOPPED", "supervisor_pid": pid}

    def restart(self) -> dict:
        stopped = self.stop()
        started = self.start()
        return {"status": started.get("status"), "stopped": stopped, "started": started}

    def supervise(self) -> int:
        api_key, relay_auth = self._credentials()
        if not api_key or not relay_auth:
            return 3
        self.relay_dir.mkdir(parents=True, exist_ok=True)
        self.pid_path.write_text(str(os.getpid()) + "\n", encoding="utf-8")
        stop_requested = {"value": False}

        def request_stop(_signum, _frame):
            stop_requested["value"] = True

        previous = {signal.SIGTERM: signal.signal(signal.SIGTERM, request_stop), signal.SIGINT: signal.signal(signal.SIGINT, request_stop)}
        relay = tunnel = None
        relay_log = tunnel_log = None
        try:
            self.config.log_dir.mkdir(parents=True, exist_ok=True)
            relay_log = (self.config.log_dir / "desktop-relay.log").open("a", encoding="utf-8")
            tunnel_log = (self.config.log_dir / "tunnel-client.log").open("a", encoding="utf-8")
            while not stop_requested["value"]:
                relay_env = {}
                if self.config.relay_config_path:
                    relay_env["DESKTOP_RELAY_CONFIG"] = self.config.relay_config_path
                relay = self._spawn(self.config.relay_command, relay_env, relay_log)
                if not self._wait_for_port(self.config.relay_host, self.config.relay_port, timeout=30):
                    self._terminate(relay)
                    relay = None
                    time.sleep(2)
                    continue
                tunnel_env = {"CONTROL_PLANE_API_KEY": api_key, "DESKTOP_RELAY_AUTH": relay_auth}
                tunnel = self._spawn(self.config.tunnel_command, tunnel_env, tunnel_log)
                self.children_path.write_text(json.dumps({"relay_pid": relay.pid, "tunnel_pid": tunnel.pid}) + "\n", encoding="utf-8")
                while not stop_requested["value"]:
                    if relay.poll() is not None or tunnel.poll() is not None:
                        break
                    time.sleep(1)
                if stop_requested["value"]:
                    break
                self._terminate(tunnel)
                self._terminate(relay)
                relay = tunnel = None
                self.children_path.unlink(missing_ok=True)
                time.sleep(2)
            return 0
        finally:
            self._terminate(tunnel)
            self._terminate(relay)
            self.children_path.unlink(missing_ok=True)
            self.pid_path.unlink(missing_ok=True)
            if relay_log:
                relay_log.close()
            if tunnel_log:
                tunnel_log.close()
            for sig, handler in previous.items():
                signal.signal(sig, handler)

    @staticmethod
    def _spawn(command, extra_env, log):
        env = os.environ.copy()
        env.pop("CONTROL_PLANE_API_KEY", None)
        env.pop("DESKTOP_RELAY_AUTH", None)
        env.update(extra_env)
        return subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)

    @staticmethod
    def _terminate(process):
        if process is None or process.poll() is not None:
            return
        try:
            process.terminate()
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
            except OSError:
                pass

    @staticmethod
    def _wait_for_port(host, port, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with socket.create_connection((host, port), timeout=1):
                    return True
            except OSError:
                time.sleep(0.5)
        return False


def cli_runtime(home: Path, action: str) -> dict:
    config = load_config(home)
    if config is None:
        return {"status": "NOT_READY", "error": "relay runtime is not configured; run relay configure first"}
    runtime = RelayRuntime(home, config)
    return getattr(runtime, action)()


def cli_supervise(home: Path) -> int:
    config = load_config(home)
    if config is None:
        return 2
    return RelayRuntime(home, config).supervise()


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(prog="pmbridge-relay-runtime")
    parser.add_argument("--supervise", action="store_true")
    parser.add_argument("--home", required=True)
    args = parser.parse_args(argv)
    config = load_config(Path(args.home))
    if config is None:
        return 2
    return RelayRuntime(Path(args.home), config).supervise() if args.supervise else 2


if __name__ == "__main__":
    raise SystemExit(main())
