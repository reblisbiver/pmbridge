import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).with_name('edge_notify.sh')


def send(chat_url: str, message: str, home: Path) -> dict:
    env = os.environ.copy()
    env['PM_CHAT_URL'] = chat_url
    env['PM_BRIDGE_LOG_DIR'] = str(home.expanduser() / 'logs')
    proc = subprocess.run(
        [str(SCRIPT), message],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    return {
        'ok': proc.returncode == 0,
        'returncode': proc.returncode,
        'error': (proc.stderr or proc.stdout or '').strip(),
    }
