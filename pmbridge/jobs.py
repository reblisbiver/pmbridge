import time
import uuid
from pathlib import Path

from . import state
from .executor import DEFAULT_MODEL, DEFAULT_REASONING_EFFORT


def tag_instruction(job_id: str, instruction: str, role: str = 'worker', access: str = None, target=None) -> str:
    lines = [
        f'[PM_BRIDGE_TASK:{job_id}]',
        f'[PM_ROLE:{role}]',
    ]
    if access is not None:
        lines.append(f'[ACCESS:{access}]')
    if target:
        lines.append(f'[TARGET:{target}]')
    lines.append(instruction.strip())
    return '\n'.join(lines)


def create_job(
    home: Path,
    project: str,
    repo: Path,
    instruction: str,
    stall_seconds: int = 1200,
    role: str = 'worker',
    access: str = None,
    network: str = 'none',
    target=None,
    model: str = DEFAULT_MODEL,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
) -> dict:
    if access not in {None, 'read', 'write'}:
        raise ValueError(f'unsupported access mode: {access}')
    if network == 'local' and access is None:
        raise ValueError('network=local requires explicit access read|write because the local-network profile also defines filesystem policy')
    if network not in {'none', 'local'}:
        raise ValueError(f'unsupported network mode: {network}')
    job_id = str(uuid.uuid4())
    jobs_dir = home.expanduser() / 'jobs'
    jobs_dir.mkdir(parents=True, exist_ok=True)
    prompt = jobs_dir / f'{job_id}.prompt.txt'
    output = jobs_dir / f'{job_id}.log'
    result = jobs_dir / f'{job_id}.result.txt'
    prompt.write_text(tag_instruction(job_id, instruction, role=role, access=access, target=target) + f'\n[NETWORK:{network}]\n', encoding='utf-8')
    output.touch()
    now = time.time()
    job = {
        'version': 1,
        'job_id': job_id,
        'project': project,
        'role': role,
        'access': access,
        'network': network,
        'target': target,
        'model': model,
        'reasoning_effort': reasoning_effort,
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
