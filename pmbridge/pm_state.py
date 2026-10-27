import json
import os
import tempfile
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path


def _path(home: Path, scope: str) -> Path:
    key = hashlib.sha256(scope.encode('utf-8')).hexdigest()
    return home.expanduser() / 'state' / 'pm-state' / f'{key}.json'


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.isoformat(timespec='seconds')


def load(home: Path, scope: str) -> dict:
    try:
        return json.loads(_path(home, scope).read_text(encoding='utf-8'))
    except Exception:
        return {'busy': False, 'reason': None, 'lease_until': None}


def save(home: Path, scope: str, data: dict) -> dict:
    path = _path(home, scope)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='pm_state.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write('\n')
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
    return data


def is_busy(home: Path, scope: str) -> bool:
    data = load(home, scope)
    if not data.get('busy'):
        return False
    lease = data.get('lease_until')
    if not lease:
        return True
    try:
        return datetime.fromisoformat(lease) > _now()
    except Exception:
        return False


def set_busy(home: Path, scope: str, reason='supervisor_work', minutes: int = 30) -> dict:
    now = _now()
    data = {
        'busy': True,
        'scope': scope,
        'reason': reason,
        'updated_at': _iso(now),
        'lease_until': _iso(now + timedelta(minutes=minutes)),
    }
    save(home, scope, data)
    data['effective_busy'] = True
    return data


def set_idle(home: Path, scope: str) -> dict:
    data = {'busy': False, 'scope': scope, 'reason': None, 'updated_at': _iso(_now()), 'lease_until': None}
    save(home, scope, data)
    data['effective_busy'] = False
    return data


def status(home: Path, scope: str) -> dict:
    data = load(home, scope)
    data['effective_busy'] = is_busy(home, scope)
    return data
