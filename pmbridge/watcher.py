import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from . import executor, state


def classify_exit(code: int) -> str:
    return 'completed' if code == 0 else 'failed'


def is_stalled(alive: bool, output_age: float, threshold: float) -> bool:
    return bool(alive and output_age >= threshold)


def notify(home: Path, job_id: str, status: str) -> None:
    subprocess.Popen(
        [sys.executable, '-m', 'pmbridge.cli', 'notify', '--home', str(home), '--job-id', job_id, '--status', status],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def run_job(home: Path, job_id: str, poll_seconds: float = 2.0) -> int:
    path = home / 'jobs' / f'{job_id}.json'
    job = state.load_job(path)
    state.safe_transition(path, watcher_pid=os.getpid())
    output = Path(job['output_file'])
    prompt = Path(job['prompt_file'])
    result = Path(job['result_file'])
    threshold = float(job.get('stall_seconds', 1200))
    cmd = executor.build_codex_command(Path(job['repo']), result)
    with prompt.open('rb') as stdin_f, output.open('ab', buffering=0) as out_f:
        proc = subprocess.Popen(cmd, stdin=stdin_f, stdout=out_f, stderr=subprocess.STDOUT, start_new_session=True)
        state.safe_transition(path, status='running', pid=proc.pid, watcher_pid=os.getpid(), last_activity_at=time.time())
        stalled = False
        while True:
            code = proc.poll()
            age = state.output_age_seconds(output)
            if code is not None:
                status = classify_exit(code)
                state.safe_transition(path, status=status, exit_code=code, finished_at=time.time(), watcher_pid=os.getpid())
                if state.claim_flag(path, 'notified_terminal'):
                    notify(home, job_id, status)
                return 0 if code == 0 else 3
            if is_stalled(True, age, threshold):
                if not stalled:
                    state.safe_transition(path, status='stalled', last_activity_at=time.time() - age)
                    if state.claim_flag(path, 'notified_stalled'):
                        notify(home, job_id, 'stalled')
                    stalled = True
            else:
                if stalled:
                    state.safe_transition(path, status='running', last_activity_at=time.time() - age, notified_stalled=False)
                    stalled = False
                else:
                    state.safe_transition(path, last_activity_at=time.time() - age)
            time.sleep(poll_seconds)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--home', type=Path, required=True)
    ap.add_argument('--job-id', required=True)
    ap.add_argument('--poll-seconds', type=float, default=2.0)
    args = ap.parse_args(argv)
    return run_job(args.home.expanduser(), args.job_id, args.poll_seconds)


if __name__ == '__main__':
    raise SystemExit(main())
