import time
import uuid
from pathlib import Path

from . import state


def tag_instruction(job_id: str, instruction: str) -> str:
    return f'[PM_BRIDGE_TASK:{job_id}]\n{instruction.strip()}'


def create_job(home: Path, project: str, repo: Path, instruction: str, stall_seconds: int = 1200) -> dict:
    job_id = str(uuid.uuid4())
    jobs_dir = home.expanduser() / 'jobs'
    jobs_dir.mkdir(parents=True, exist_ok=True)
    prompt = jobs_dir / f'{job_id}.prompt.txt'
    output = jobs_dir / f'{job_id}.log'
    result = jobs_dir / f'{job_id}.result.txt'
    prompt.write_text(tag_instruction(job_id, instruction) + '\n', encoding='utf-8')
    output.touch()
    now = time.time()
    job = {
        'version': 1,
        'job_id': job_id,
        'project': project,
        'status': 'starting',
        'repo': str(repo.resolve()),
        'pid': None,
        'watcher_pid': None,
        'started_at': now,
        'updated_at': now,
        'last_activity_at': now,
        'stall_seconds': int(stall_seconds),
        'prompt_file': str(prompt),
        'output_file': str(output),
        'result_file': str(result),
        'exit_code': None,
        'notified_stalled': False,
        'notified_terminal': False,
    }
    state.write_job(jobs_dir / f'{job_id}.json', job)
    return job
