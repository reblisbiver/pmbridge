import json
import subprocess
from pathlib import Path

from . import state

DEFAULT_PREVIEW_CHARS = 12000
DEFAULT_CHANGED_FILE_LIMIT = 100


def capture_head(repo: Path):
    try:
        proc = subprocess.run(['git','-C',str(repo),'rev-parse','HEAD'], capture_output=True, text=True, timeout=5)
        return proc.stdout.strip() if proc.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _file_meta(path_value):
    if not path_value:
        return {'path': None, 'exists': False, 'bytes': 0}
    path = Path(path_value)
    try:
        size = path.stat().st_size
        return {'path': str(path), 'exists': True, 'bytes': size}
    except OSError:
        return {'path': str(path), 'exists': False, 'bytes': 0}


def _result_view(path_value, full_result=False, preview_chars=DEFAULT_PREVIEW_CHARS):
    meta = _file_meta(path_value)
    if not meta['exists']:
        return {**meta, 'text': None, 'truncated': False}
    try:
        text = Path(meta['path']).read_text(encoding='utf-8', errors='replace')
    except OSError:
        return {**meta, 'text': None, 'truncated': False}
    if full_result or len(text) <= preview_chars:
        return {**meta, 'text': text, 'truncated': False}
    return {**meta, 'text': text[:preview_chars], 'truncated': True, 'total_chars': len(text)}


def _git_diff(repo, start_head, end_head, changed_file_limit=DEFAULT_CHANGED_FILE_LIMIT):
    base = {'start_head': start_head, 'end_head': end_head, 'changed_files': [], 'changed_file_count': None, 'changed_files_truncated': False, 'diffstat': None}
    if not repo or not start_head or not end_head:
        return base
    try:
        names = subprocess.run(['git','-C',str(repo),'diff','--name-only',start_head,end_head], capture_output=True, text=True, timeout=10)
        stat = subprocess.run(['git','-C',str(repo),'diff','--stat',start_head,end_head], capture_output=True, text=True, timeout=10)
        if names.returncode != 0 or stat.returncode != 0:
            return base
        files = [line for line in names.stdout.splitlines() if line]
        return {
            **base,
            'changed_files': files[:changed_file_limit],
            'changed_file_count': len(files),
            'changed_files_truncated': len(files) > changed_file_limit,
            'diffstat': stat.stdout.strip() or None,
        }
    except (OSError, subprocess.SubprocessError):
        return base


def inspect_job(home: Path, job_id: str, full_result: bool = False) -> dict:
    home = home.expanduser()
    job = state.load_job(home/'jobs'/f'{job_id}.json')
    log = _file_meta(job.get('output_file'))
    result = _result_view(job.get('result_file'), full_result=full_result)
    git = _git_diff(job.get('repo'), job.get('start_head'), job.get('end_head'))
    metadata_keys = ('job_id','project','role','status','target','access','network','model','reasoning_effort','started_at','finished_at','exit_code','pid','watcher_pid')
    return {
        'status': 'READY',
        'job': {k: job.get(k) for k in metadata_keys if k in job},
        'result': result,
        'git': git,
        'raw_evidence': {
            'job': _file_meta(home/'jobs'/f'{job_id}.json'),
            'prompt': _file_meta(job.get('prompt_file')),
            'log': log,
            'result': {k: result.get(k) for k in ('path','exists','bytes')},
        },
    }
