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


def pending_events(home: Path, create: bool = True):
    pending, _ = _dirs(home)
    if create:
        pending.mkdir(parents=True, exist_ok=True)
    if not pending.exists():
        return []
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
    last_signature_by_conversation = {}
    safe_since_by_conversation = {}
    with lock.open('a+') as fh:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {'status': 'LOCKED', 'delivered': 0, 'pending': len(pending_events(home))}
        while True:
            paths = sorted(pending.glob('*.json'))
            if not paths:
                return {'status': 'EMPTY', 'delivered': delivered_count, 'pending': 0}
            # The queue is globally ordered on disk, but only the oldest event
            # for each chat is eligible to compete for delivery. This keeps a
            # blocked chat from holding unrelated chats behind it while still
            # preserving FIFO within every conversation.
            heads = []
            seen_conversations = set()
            for path in paths:
                try:
                    event = json.loads(path.read_text(encoding='utf-8'))
                    cfg = config.load_project(home, event['project'])
                    chat_url = cfg.get('chat_url')
                    conversation = ('chat', chat_url) if chat_url else ('project', event['project'])
                except Exception:
                    shutil.move(str(path), str(delivered / (path.stem + '.invalid.json')))
                    continue
                if conversation in seen_conversations:
                    continue
                seen_conversations.add(conversation)
                heads.append((path, event, cfg, conversation))

            if not heads:
                continue

            candidate = None
            blocked_status = None
            failed_conversations = set()
            for path, event, cfg, conversation in heads:
                if pm_state.is_busy(home, cfg['chat_url']):
                    safe_since_by_conversation.pop(conversation, None)
                    if blocked_status is None:
                        blocked_status = 'PM_BUSY'
                    continue
                ui = transport_edge.ui_state(cfg['chat_url'])
                if not ui.get('reachable') or ui.get('composer_nonempty') or ui.get('generating'):
                    safe_since_by_conversation.pop(conversation, None)
                    last_signature_by_conversation[conversation] = ui.get('signature')
                    if blocked_status is None:
                        blocked_status = 'UI_BUSY'
                    continue
                now = time.monotonic()
                signature = ui.get('signature')
                if signature != last_signature_by_conversation.get(conversation):
                    last_signature_by_conversation[conversation] = signature
                    safe_since_by_conversation[conversation] = now
                if conversation not in safe_since_by_conversation:
                    safe_since_by_conversation[conversation] = now
                quiet = quiet_focused_seconds if (ui.get('focused') or ui.get('visibility') == 'visible') else quiet_background_seconds
                if now - safe_since_by_conversation[conversation] < quiet:
                    if blocked_status is None:
                        blocked_status = 'UI_QUIET_WAIT'
                    continue
                result = transport_edge.send(cfg['chat_url'], _message(event), home)
                if not result.get('ok'):
                    failed_conversations.add(conversation)
                    if blocked_status is None:
                        blocked_status = 'DELIVERY_FAILED'
                    continue
                candidate = (path, event, cfg, conversation)
                break

            if candidate is None:
                if time.monotonic() >= deadline:
                    return {'status': blocked_status or 'UI_BUSY', 'delivered': delivered_count, 'pending': len(paths)}
                time.sleep(poll_seconds)
                continue

            path, event, cfg, conversation = candidate
            shutil.move(str(path), str(delivered / path.name))
            delivered_count += 1
            last_signature_by_conversation.pop(conversation, None)
            safe_since_by_conversation.pop(conversation, None)
            time.sleep(0.5)
