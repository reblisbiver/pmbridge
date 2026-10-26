import os
import plistlib
import subprocess
from pathlib import Path

LABEL = 'com.pmbridge.recovery'


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
