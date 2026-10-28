import json
from datetime import datetime, timezone
from pathlib import Path

from . import config, events, executor, ledger, state

ACTIVE = {'starting', 'running', 'stalled'}
TERMINAL = {'completed', 'failed', 'interrupted'}


def _project_root(home: Path, project: str) -> Path:
    return home.expanduser() / 'projects' / project


def _history_path(home: Path, project: str) -> Path:
    return _project_root(home, project) / 'bindings' / 'history.jsonl'


def _append_history(path: Path, entry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + '\n')


def rebind(home: Path, project: str, new_chat_url: str, source: str = 'manual') -> dict:
    home = home.expanduser()
    cfg = config.load_project(home, project)
    previous = cfg.get('chat_url')
    old_version = int(cfg.get('binding_version', 1))
    new_version = old_version + 1
    changed_at = datetime.now(timezone.utc).isoformat(timespec='seconds')
    entry = {
        'binding_version': new_version,
        'changed_at': changed_at,
        'source': source,
        'previous_chat_url': previous,
        'new_chat_url': new_chat_url,
    }
    cfg['chat_url'] = new_chat_url
    cfg['binding_version'] = new_version
    cfg['binding_updated_at'] = changed_at
    config.save_project(home, cfg)
    _append_history(_history_path(home, project), entry)
    return {
        'status': 'READY',
        'project': project,
        'chat_url': new_chat_url,
        'binding_version': new_version,
        'previous_chat_url': previous,
    }


def _job_summary(job: dict) -> dict:
    keys = ('job_id','status','role','target','access','network','model','reasoning_effort','pid','watcher_pid','started_at','finished_at','exit_code')
    return {k: job.get(k) for k in keys if k in job}


def handoff(home: Path, project: str, recent_limit: int = 8) -> dict:
    home = home.expanduser()
    cfg = config.load_project(home, project)
    active = []
    recent = []
    jobs_dir = home / 'jobs'
    if jobs_dir.exists():
        for path in jobs_dir.glob('*.json'):
            try:
                job = state.load_job(path)
            except Exception:
                continue
            if job.get('project') != project:
                continue
            if job.get('status') in ACTIVE:
                active.append(_job_summary(job))
            elif job.get('status') in TERMINAL:
                recent.append(_job_summary(job))
    active.sort(key=lambda x: x.get('started_at') or 0)
    recent.sort(key=lambda x: x.get('finished_at') or x.get('started_at') or 0, reverse=True)
    pending = [e for e in events.pending_events(home) if e.get('project') == project]
    return {
        'status': 'READY',
        'project': project,
        'repo': cfg.get('repo'),
        'active_binding': {
            'url': cfg.get('chat_url'),
            'version': int(cfg.get('binding_version', 1)),
            'updated_at': cfg.get('binding_updated_at'),
        },
        'execution_defaults': {
            'model': cfg.get('default_model') or executor.DEFAULT_MODEL,
            'reasoning_effort': cfg.get('default_reasoning_effort') or executor.DEFAULT_REASONING_EFFORT,
            'stall_seconds': cfg.get('stall_seconds'),
        },
        'active_jobs': active,
        'recent_jobs': recent[:recent_limit],
        'pending_events': pending,
        'ledger': ledger.load(home, project),
    }
