import os
import plistlib
import subprocess
from pathlib import Path

LABEL = 'com.pmbridge.recovery'
RELAY_LABEL = 'com.pmbridge.relay'


def plist_path() -> Path:
    return Path.home() / 'Library' / 'LaunchAgents' / f'{LABEL}.plist'


def render_plist(home: Path) -> str:
    home = home.expanduser()
    payload = {
        'Label': LABEL,
        'ProgramArguments': [str(home / 'bin' / 'pmbridge'), 'recovery', '--home', str(home), '--json'],
        'RunAtLoad': True,
        'StartInterval': 60,
        'StandardOutPath': str(home / 'logs' / 'recovery.out.log'),
        'StandardErrorPath': str(home / 'logs' / 'recovery.err.log'),
    }
    return plistlib.dumps(payload, fmt=plistlib.FMT_XML).decode('utf-8')


def install(home: Path, destination: Path = None) -> Path:
    destination = destination or plist_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_plist(home), encoding='utf-8')
    return destination


def load(destination: Path = None) -> subprocess.CompletedProcess:
    destination = destination or plist_path()
    uid = os.getuid()
    subprocess.run(['launchctl', 'bootout', f'gui/{uid}', str(destination)], capture_output=True, text=True, check=False)
    return subprocess.run(['launchctl', 'bootstrap', f'gui/{uid}', str(destination)], capture_output=True, text=True, check=False)


def relay_plist_path() -> Path:
    return Path.home() / 'Library' / 'LaunchAgents' / f'{RELAY_LABEL}.plist'


def render_relay_plist(home: Path, config_path: Path = None) -> str:
    home = Path(home).expanduser().resolve()
    config_path = config_path or (home / 'relay' / 'config.json')
    payload = {
        'Label': RELAY_LABEL,
        'ProgramArguments': [
            str(home / 'bin' / 'pmbridge'), 'relay', 'supervisor',
            '--home', str(home), '--config', str(config_path),
        ],
        'RunAtLoad': True,
        'KeepAlive': True,
        'ThrottleInterval': 5,
        'StandardOutPath': str(home / 'relay' / 'logs' / 'supervisor.out.log'),
        'StandardErrorPath': str(home / 'relay' / 'logs' / 'supervisor.err.log'),
    }
    return plistlib.dumps(payload, fmt=plistlib.FMT_XML).decode('utf-8')


def install_relay(home: Path, destination: Path = None) -> Path:
    destination = destination or relay_plist_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_relay_plist(home), encoding='utf-8')
    return destination


def relay_enable(home: Path, destination: Path = None) -> dict:
    destination = install_relay(home, destination)
    uid = os.getuid()
    subprocess.run(['launchctl', 'bootout', f'gui/{uid}', str(destination)], capture_output=True, text=True, check=False)
    loaded = subprocess.run(['launchctl', 'bootstrap', f'gui/{uid}', str(destination)], capture_output=True, text=True, check=False)
    return {'status': 'ENABLED' if loaded.returncode == 0 else 'NOT_READY', 'label': RELAY_LABEL, 'plist': str(destination)}


def relay_disable(home: Path, destination: Path = None) -> dict:
    destination = destination or relay_plist_path()
    uid = os.getuid()
    subprocess.run(['launchctl', 'bootout', f'gui/{uid}', str(destination)], capture_output=True, text=True, check=False)
    try:
        destination.unlink()
    except FileNotFoundError:
        pass
    return {'status': 'DISABLED', 'label': RELAY_LABEL, 'plist': str(destination)}


def relay_status(destination: Path = None) -> dict:
    destination = destination or relay_plist_path()
    uid = os.getuid()
    loaded = subprocess.run(['launchctl', 'print', f'gui/{uid}/{RELAY_LABEL}'], capture_output=True, text=True, check=False)
    return {'status': 'ENABLED' if loaded.returncode == 0 else 'DISABLED', 'label': RELAY_LABEL, 'plist': str(destination), 'loaded': loaded.returncode == 0}
