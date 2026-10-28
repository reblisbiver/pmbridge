import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _path(home: Path, project: str) -> Path:
    return home.expanduser()/'projects'/project/'pm-ledger.json'


def load(home: Path, project: str):
    path = _path(home, project)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding='utf-8'))


def _write(home: Path, project: str, data) -> dict:
    path = _path(home, project)
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = load(home, project)
    version = int(previous.get('version', 0)) + 1 if isinstance(previous, dict) else 1
    payload = {
        'version': version,
        'updated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'data': data,
    }
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    os.replace(tmp, path)
    return payload


def replace(home: Path, project: str, data) -> dict:
    return _write(home, project, data)


def patch(home: Path, project: str, fields: dict) -> dict:
    current = load(home, project)
    data = current.get('data', {}) if isinstance(current, dict) else {}
    if not isinstance(data, dict):
        raise ValueError('ledger patch requires the current ledger data to be a JSON object; use replace for other JSON values')
    merged = dict(data)
    merged.update(fields)
    return _write(home, project, merged)
