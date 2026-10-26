import fcntl
import hashlib
import json
import os
import shutil
import time
import uuid
from pathlib import Path

from . import config, pm_state, state, transport_edge


def _dirs(home: Path):
    root = home.expanduser() / 'events'
    return root / 'pending', root / 'delivered'


def _event_key(job: dict, status_text: str) -> str:
    anchor = job.get('finished_at') if status_text in {'completed', 'failed', 'interrupted'} else job.get('last_activity_at')
    raw = f"{job.get('job_id')}|{status_text}|{anchor}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _claim_event_key(home: Path, key: str) -> bool:
    root = home.expanduser() / 'state' / 'event-keys'
    root.mkdir(parents=True, exist_ok=True)
    marker = root / key
    try:
        marker.touch(exist_ok=False)
        return True
    except FileExistsError:
        return False


def enqueue_job_event(home: Path, job_id: str, status_text: str) -> dict:
    home = home.expanduser()
    job = state.load_job(home / 'jobs' / f'{job_id}.json')
    key = _event_key(job, status_text)
    pending, _ = _dirs(home)
    pending.mkdir(parents=True, exist_ok=True)
    if not _claim_event_key(home, key):
        for path in sorted(pending.glob('*.json')):
            try:
                existing = json.loads(path.read_text(encoding='utf-8'))
                if existing.get('dedupe_key') == key:
                    return existing
            except Exception:
                continue
        return {'status': 'DEDUPED', 'dedupe_key': key}
    event = {
        'event_id': str(uuid.uuid4()),
        'dedupe_key': key,
        'created_at_ns': time.time_ns(),
        'job_id': job_id,
        'project': job['project'],
        'role': job.get('role'),
        'target': job.get('target'),
        'status': status_text,
    }
    name = f"{event['created_at_ns']:020d}-{event['event_id']}.json"
    path = pending / name
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(event, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(tmp, path)
    return event


def pending_events(home: Path):
    pending, _ = _dirs(home)
    pending.mkdir(parents=True, exist_ok=True)
    result = []
    for path in sorted(pending.glob('*.json')):
        try:
            result.append(json.loads(path.read_text(encoding='utf-8')))
        except Exception:
            pass
    return result


def _message(event: dict) -> str:
    msg = f"PM_JOB_STATUS {event['job_id']} {event['status']}"
    if event.get('role'):
        msg += f" role={event['role']}"
    if event.get('target'):
        msg += f" target={event['target']}"
    return msg


def drain(home: Path, wait_seconds: float = 0.0, poll_seconds: float = 0.75, quiet_focused_seconds: float = 0.0, quiet_background_seconds: float = 0.0) -> dict:
    home = home.expanduser()
    pending, delivered = _dirs(home)
    pending.mkdir(parents=True, exist_ok=True)
    delivered.mkdir(parents=True, exist_ok=True)
    lock = home / 'state' / 'event-drain.lock'
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + max(0.0, wait_seconds)
    delivered_count = 0
    last_signature = None
    safe_since = None
    with lock.open('a+') as fh:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {'status': 'LOCKED', 'delivered': 0, 'pending': len(pending_events(home))}
        while True:
            paths = sorted(pending.glob('*.json'))
            if not paths:
                return {'status': 'EMPTY', 'delivered': delivered_count, 'pending': 0}
            if pm_state.is_busy(home):
                safe_since = None
                if time.monotonic() >= deadline:
                    return {'status': 'PM_BUSY', 'delivered': delivered_count, 'pending': len(paths)}
                time.sleep(poll_seconds)
                continue
            path = paths[0]
            try:
                event = json.loads(path.read_text(encoding='utf-8'))
                cfg = config.load_project(home, event['project'])
            except Exception:
                shutil.move(str(path), str(delivered / (path.stem + '.invalid.json')))
                continue
            ui = transport_edge.ui_state(cfg['chat_url'])
            if not ui.get('reachable') or ui.get('composer_nonempty') or ui.get('generating'):
                safe_since = None
                last_signature = ui.get('signature')
                if time.monotonic() >= deadline:
                    return {'status': 'UI_BUSY', 'delivered': delivered_count, 'pending': len(paths)}
                time.sleep(poll_seconds)
                continue
            now = time.monotonic()
            signature = ui.get('signature')
            if signature != last_signature:
                last_signature = signature
                safe_since = now
            if safe_since is None:
                safe_since = now
            quiet = quiet_focused_seconds if (ui.get('focused') or ui.get('visibility') == 'visible') else quiet_background_seconds
            if now - safe_since < quiet:
                if now >= deadline:
                    return {'status': 'UI_QUIET_WAIT', 'delivered': delivered_count, 'pending': len(paths)}
                time.sleep(poll_seconds)
                continue
            result = transport_edge.send(cfg['chat_url'], _message(event), home)
            if not result.get('ok'):
                if time.monotonic() >= deadline:
                    return {'status': 'DELIVERY_FAILED', 'delivered': delivered_count, 'pending': len(paths)}
                time.sleep(max(1.0, poll_seconds))
                continue
            shutil.move(str(path), str(delivered / path.name))
            delivered_count += 1
            last_signature = None
            safe_since = None
            time.sleep(0.5)
