import json
from datetime import datetime, timezone
from pathlib import Path

from . import config, events, executor, ledger, pm_state, state

ACTIVE = {'starting', 'running', 'stalled'}
TERMINAL = {'completed', 'failed', 'interrupted'}
CHARTER_PATH = 'docs/pm-operating-charter.md'


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


def _collect_jobs(home: Path, project: str, recent_limit: int = 8):
    home = home.expanduser()
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
                active.append((_job_summary(job), _evidence_ref(job)))
            elif job.get('status') in TERMINAL:
                recent.append((_job_summary(job), _evidence_ref(job)))
    active.sort(key=lambda x: x[0].get('started_at') or 0)
    recent.sort(key=lambda x: x[0].get('finished_at') or x[0].get('started_at') or 0, reverse=True)
    return (
        [entry[0] for entry in active],
        [entry[0] for entry in recent[:recent_limit]],
        [entry[1] for entry in active] + [entry[1] for entry in recent[:recent_limit]],
    )


def _evidence_ref(job):
    entry = {'job_id': job.get('job_id')}
    for key in ('prompt_file', 'output_file', 'result_file'):
        if job.get(key):
            entry[key] = job[key]
    return entry


def takeover(home: Path, project: str, recent_limit: int = 8) -> dict:
    """Build the canonical read-only four-layer takeover view.

    This composes existing project, execution, and runtime state. It is not a
    second state store and intentionally does not include prompt/result text.
    """
    home = home.expanduser()
    cfg = config.load_project(home, project)
    active, recent, evidence = _collect_jobs(home, project, recent_limit=recent_limit)
    pending = [e for e in events.pending_events(home, create=False) if e.get('project') == project]
    chat_url = cfg.get('chat_url')
    scope = chat_url or project
    active_binding = {
        'url': chat_url,
        'version': int(cfg.get('binding_version', 1)),
        'updated_at': cfg.get('binding_updated_at'),
    }
    working_state = ledger.load(home, project)
    return {
        'status': 'READY',
        'project': {
            'name': project,
            'repo': cfg.get('repo'),
            'working_state': working_state,
        },
        'supervision': {
            'role': 'product_manager',
            'charter': {'path': CHARTER_PATH, 'read_first': True},
            'continuity': {
                'canonical_view': 'takeover',
                'compatibility_view': 'handoff',
            },
        },
        'execution': {
            'defaults': {
                'model': cfg.get('default_model') or executor.DEFAULT_MODEL,
                'reasoning_effort': cfg.get('default_reasoning_effort') or executor.DEFAULT_REASONING_EFFORT,
                'stall_seconds': cfg.get('stall_seconds'),
            },
            'active_jobs': active,
            'recent_jobs': recent,
            'evidence': evidence,
        },
        'runtime': {
            'binding': active_binding,
            'callbacks': {'pending': pending},
            'pm_state': pm_state.status(home, scope),
            'edge': {
                'transport': 'edge',
                'configured': bool(chat_url),
                'delivery_guard': ['pm_idle', 'ui_idle', 'composer_empty', 'quiet_window'],
            },
            'watchers': [
                {'job_id': job.get('job_id'), 'status': job.get('status'), 'pid': job.get('pid'), 'watcher_pid': job.get('watcher_pid')}
                for job in active
            ],
            'recovery': {'entrypoint': 'pmbridge recovery', 'available': True},
        },
    }


def handoff(home: Path, project: str, recent_limit: int = 8) -> dict:
    """Compatibility wrapper for the canonical ``takeover`` read view."""
    view = takeover(home, project, recent_limit=recent_limit)
    return {
        'status': view['status'],
        'project': view['project']['name'],
        'repo': view['project']['repo'],
        'active_binding': view['runtime']['binding'],
        'execution_defaults': view['execution']['defaults'],
        'active_jobs': view['execution']['active_jobs'],
        'recent_jobs': view['execution']['recent_jobs'],
        'pending_events': view['runtime']['callbacks']['pending'],
        'ledger': view['project']['working_state'],
        'takeover': view,
    }
