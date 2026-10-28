import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from . import config, ledger, state


def _epoch(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()
    except (TypeError, ValueError):
        return None


def _size(path_value):
    if not path_value:
        return 0
    try: return Path(path_value).stat().st_size
    except OSError: return 0


def _event_time(event):
    if event.get('created_at_ns') is not None:
        try: return int(event['created_at_ns']) / 1_000_000_000
        except (ValueError, TypeError): pass
    try: return float(event.get('delivered_at'))
    except (ValueError, TypeError): return None


def report(home: Path, project: str) -> dict:
    home = home.expanduser()
    cfg = config.load_project(home, project)
    since = _epoch(cfg.get('binding_updated_at'))
    jobs = []
    jobs_dir = home/'jobs'
    if jobs_dir.exists():
        for path in jobs_dir.glob('*.json'):
            try: job = state.load_job(path)
            except Exception: continue
            if job.get('project') != project: continue
            started = job.get('started_at')
            if since is not None and started is not None and float(started) < since: continue
            jobs.append(job)
    callbacks = 0
    delivered = home/'events'/'delivered'
    if delivered.exists():
        for path in delivered.glob('*.json'):
            try: event=json.loads(path.read_text(encoding='utf-8'))
            except Exception: continue
            if event.get('project') != project: continue
            when=_event_time(event)
            if since is not None and when is not None and when < since: continue
            callbacks += 1
    led = ledger.load(home, project)
    ledger_path = home/'projects'/project/'pm-ledger.json'
    return {
        'status': 'READY',
        'project': project,
        'window': {'basis':'current_binding' if since is not None else 'all_history', 'since': cfg.get('binding_updated_at')},
        'jobs': len(jobs),
        'jobs_by_status': dict(Counter(j.get('status') for j in jobs)),
        'jobs_by_role': dict(Counter(j.get('role') for j in jobs if j.get('role'))),
        'callbacks': callbacks,
        'raw_evidence_bytes': sum(_size(j.get('output_file')) for j in jobs),
        'result_bytes': sum(_size(j.get('result_file')) for j in jobs),
        'ledger': None if led is None else {'version':led.get('version'),'updated_at':led.get('updated_at'),'bytes':_size(ledger_path)},
    }
