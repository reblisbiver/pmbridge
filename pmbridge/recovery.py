import os
import subprocess
import sys
import time
from pathlib import Path

from . import state

ACTIVE = {'starting', 'running', 'stalled'}


def _result_exists(job: dict) -> bool:
    value = job.get('result_file')
    return bool(value and Path(value).is_file())


def recovery_action(job: dict) -> str:
    status = job.get('status')
    if status in state.TERMINAL:
        return 'notify' if not job.get('notified_terminal') else 'none'
    if status not in ACTIVE:
        return 'none'
    if not state.process_alive(job.get('pid')):
        return 'complete' if _result_exists(job) else 'interrupt'
    if state.process_alive(job.get('watcher_pid')):
        return 'none'
    return 'reattach'


def scan(home: Path) -> dict:
    jobs_dir = home.expanduser() / 'jobs'
    jobs_dir.mkdir(parents=True, exist_ok=True)
    summary = {'checked': 0, 'reattached': 0, 'completed': 0, 'interrupted': 0, 'notified': 0}
    for path in sorted(jobs_dir.glob('*.json')):
        summary['checked'] += 1
        job = state.load_job(path)
        action = recovery_action(job)
        if action == 'none':
            continue
        if action == 'notify':
            if state.claim_flag(path, 'notified_terminal'):
                subprocess.Popen(
                    [sys.executable, '-m', 'pmbridge.cli', 'notify', '--home', str(home), '--job-id', job['job_id'], '--status', job['status']],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
                )
                summary['notified'] += 1
            continue
        if action == 'complete':
            result_path = Path(job['result_file'])
            finished_at = result_path.stat().st_mtime if result_path.exists() else time.time()
            state.safe_transition(path, status='completed', finished_at=finished_at)
            if state.claim_flag(path, 'notified_terminal'):
                subprocess.Popen(
                    [sys.executable, '-m', 'pmbridge.cli', 'notify', '--home', str(home), '--job-id', job['job_id'], '--status', 'completed'],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
                )
                summary['notified'] += 1
            summary['completed'] += 1
            continue
        if action == 'interrupt':
            state.safe_transition(path, status='interrupted')
            if state.claim_flag(path, 'notified_terminal'):
                subprocess.Popen(
                    [sys.executable, '-m', 'pmbridge.cli', 'notify', '--home', str(home), '--job-id', job['job_id'], '--status', 'interrupted'],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
                )
            summary['interrupted'] += 1
            continue
        watcher = subprocess.Popen(
            [sys.executable, '-m', 'pmbridge.watcher', '--home', str(home), '--job-id', job['job_id'], '--attach'],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
        )
        state.safe_transition(path, watcher_pid=watcher.pid)
        summary['reattached'] += 1
    return summary
