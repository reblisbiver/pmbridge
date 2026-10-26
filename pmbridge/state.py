import fcntl
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path

TERMINAL = {'completed', 'failed', 'interrupted'}


@contextmanager
def _locked(path: Path):
    lock = path.with_suffix(path.suffix + '.lock')
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('a+') as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(tmp, path)


def write_job(path: Path, job: dict) -> Path:
    with _locked(path):
        _atomic_write(path, job)
    return path


def load_job(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def update_job(path: Path, **fields) -> dict:
    with _locked(path):
        job = load_job(path)
        job.update(fields)
        job['updated_at'] = time.time()
        _atomic_write(path, job)
        return job


def safe_transition(path: Path, **fields) -> dict:
    with _locked(path):
        job = load_job(path)
        current = job.get('status')
        requested = fields.get('status', current)
        if current in TERMINAL and requested != current:
            fields = {k: v for k, v in fields.items() if k != 'status'}
        job.update(fields)
        job['updated_at'] = time.time()
        _atomic_write(path, job)
        return job


def claim_flag(path: Path, flag: str) -> bool:
    with _locked(path):
        job = load_job(path)
        if job.get(flag):
            return False
        job[flag] = True
        job['updated_at'] = time.time()
        _atomic_write(path, job)
        return True


def process_alive(pid) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except (ProcessLookupError, PermissionError, ValueError, TypeError):
        return False


def output_age_seconds(path: Path, now=None) -> float:
    if not path.exists():
        return float('inf')
    now = time.time() if now is None else now
    return max(0.0, now - path.stat().st_mtime)
