import argparse
import json
import os
import subprocess
from pathlib import Path

from . import binding, config, doctor, events, executor, gitops, jobs, launchd, pm_state, recovery, runtime, state, transport_edge, watcher


def emit(payload, as_json):
    if as_json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def home_path(value=None):
    return Path(value or os.environ.get('PMBRIDGE_HOME', '~/.pmbridge')).expanduser().resolve()


def bootstrap(args):
    repo_result = gitops.ensure_repo(Path(args.repo), init_repo=args.init_repo)
    if repo_result['status'] != 'READY':
        return repo_result
    repo = Path(repo_result['repo'])
    name = args.name or config.default_project_name(repo)
    chat_url = None
    if args.chat_url and args.chat_url != 'auto':
        chat_url = args.chat_url
    elif args.chat_bind_text:
        binding = transport_edge.find_chat_by_texts(args.chat_bind_text, attempts=4, delay=0.25, timeout=2.0)
        if binding.get('status') != 'FOUND':
            return binding
        chat_url = binding['url']
    elif args.chat_bind_token:
        binding = transport_edge.find_chat_by_token(args.chat_bind_token, attempts=4, delay=0.25)
        if binding.get('status') != 'FOUND':
            return binding
        chat_url = binding['url']
    else:
        return {'status': 'NEEDS_CHAT_BINDING', 'message': 'Provide --chat-bind-text from recent user messages, --chat-bind-token, or an explicit --chat-url.'}
    cfg = {
        'version': 1,
        'name': name,
        'repo': str(repo),
        'chat_url': chat_url,
        'stall_seconds': args.stall_seconds,
        'default_model': executor.DEFAULT_MODEL,
        'default_reasoning_effort': executor.DEFAULT_REASONING_EFFORT,
    }
    home = home_path(args.home)
    config_path = config.save_project(home, cfg)
    runtime_result = runtime.install(home)
    plist = launchd.install(home)
    load_result = launchd.load(plist)
    return {
        'status': 'READY',
        'project': name,
        'config': str(config_path),
        'repo_created': repo_result['created'],
        'runtime': runtime_result['command'],
        'supervisor_loaded': load_result.returncode == 0,
        'next': ['doctor', 'smoke'],
    }


def spawn_watcher(home: Path, job_id: str):
    return subprocess.Popen(
        [str(home/'bin'/'pmbridge'), 'watch', '--home', str(home), '--job-id', job_id],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
    )


def run_project(
    home: Path,
    project: str,
    instruction: str,
    role: str = 'worker',
    access: str = None,
    network: str = 'none',
    target=None,
    model: str = executor.DEFAULT_MODEL,
    reasoning_effort: str = executor.DEFAULT_REASONING_EFFORT,
) -> dict:
    cfg = config.load_project(home, project)
    job = jobs.create_job(
        home, project, Path(cfg['repo']), instruction, int(cfg.get('stall_seconds', 1200)),
        role=role, access=access, network=network, target=target, model=model, reasoning_effort=reasoning_effort,
    )
    proc = spawn_watcher(home, job['job_id'])
    state.safe_transition(home/'jobs'/f"{job['job_id']}.json", watcher_pid=proc.pid)
    return {
        'status': 'STARTED', 'project': project, 'job_id': job['job_id'], 'watcher_pid': proc.pid,
        'role': role, 'access': access, 'network': network, 'target': target, 'model': model, 'reasoning_effort': reasoning_effort,
    }


def spawn_event_drain(home: Path, wait_seconds: int = 180):
    return subprocess.Popen(
        [str(home/'bin'/'pmbridge'), 'drain', '--home', str(home), '--wait-seconds', str(wait_seconds), '--json'],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
    )


def notify_job(home: Path, job_id: str, status_text: str) -> dict:
    event = events.enqueue_job_event(home, job_id, status_text)
    if event.get('status') != 'DEDUPED':
        try:
            spawn_event_drain(home)
        except FileNotFoundError:
            pass
    return {'ok': True, 'queued': True, 'event': event}


def rebind_project(home: Path, args) -> dict:
    if args.chat_url:
        url = args.chat_url
        source = 'explicit-url'
    elif args.chat_bind_text:
        found = transport_edge.find_chat_by_texts(args.chat_bind_text, attempts=4, delay=0.25, timeout=2.0)
        if found.get('status') != 'FOUND':
            return found
        url = found['url']
        source = 'chat-bind-text'
    else:
        return {'status':'NEEDS_CHAT_BINDING'}
    result = binding.rebind(home, args.project, url, source=source)
    result['doctor'] = doctor.check(home, args.project)
    if result['doctor'].get('status') != 'READY':
        result['status'] = 'NOT_READY'
    return result


def build_parser():
    ap = argparse.ArgumentParser(prog='pmbridge')
    sub = ap.add_subparsers(dest='command', required=True)

    bp = sub.add_parser('bootstrap')
    bp.add_argument('--repo', required=True)
    bp.add_argument('--chat-url')
    bp.add_argument('--chat-bind-token')
    bp.add_argument('--chat-bind-text', action='append')
    bp.add_argument('--name')
    bp.add_argument('--stall-seconds', type=int, default=1200)
    bp.add_argument('--init-repo', action='store_true')
    bp.add_argument('--home')
    bp.add_argument('--json', action='store_true')

    dp = sub.add_parser('doctor')
    dp.add_argument('project')
    dp.add_argument('--home')
    dp.add_argument('--json', action='store_true')

    rp = sub.add_parser('run')
    rp.add_argument('project')
    group = rp.add_mutually_exclusive_group(required=True)
    group.add_argument('--instruction')
    group.add_argument('--file', type=Path)
    rp.add_argument('--role', default='worker')
    rp.add_argument('--access', choices=['read','write'])
    rp.add_argument('--network', choices=['none','local'], default='none')
    rp.add_argument('--target')
    rp.add_argument('--model', default=executor.DEFAULT_MODEL)
    rp.add_argument('--reasoning-effort', default=executor.DEFAULT_REASONING_EFFORT)
    rp.add_argument('--home')
    rp.add_argument('--json', action='store_true')

    sp = sub.add_parser('smoke')
    sp.add_argument('project')
    sp.add_argument('--home')
    sp.add_argument('--json', action='store_true')

    np = sub.add_parser('notify')
    np.add_argument('--job-id', required=True)
    np.add_argument('--status', required=True)
    np.add_argument('--home')
    np.add_argument('--json', action='store_true')

    rec = sub.add_parser('recovery')
    rec.add_argument('--home')
    rec.add_argument('--json', action='store_true')

    wp = sub.add_parser('watch')
    wp.add_argument('--job-id', required=True)
    wp.add_argument('--home')
    wp.add_argument('--attach', action='store_true')
    wp.add_argument('--json', action='store_true')

    dr = sub.add_parser('drain')
    dr.add_argument('--home')
    dr.add_argument('--wait-seconds', type=float, default=0.0)
    dr.add_argument('--quiet-focused-seconds', type=float, default=12.0)
    dr.add_argument('--quiet-background-seconds', type=float, default=4.0)
    dr.add_argument('--json', action='store_true')

    rb = sub.add_parser('rebind')
    rb.add_argument('project')
    rb.add_argument('--chat-url')
    rb.add_argument('--chat-bind-text', action='append')
    rb.add_argument('--home')
    rb.add_argument('--json', action='store_true')

    ho = sub.add_parser('handoff')
    ho.add_argument('project')
    ho.add_argument('--home')
    ho.add_argument('--json', action='store_true')

    pp = sub.add_parser('pm')
    psub = pp.add_subparsers(dest='pm_command', required=True)
    pb = psub.add_parser('busy'); pb.add_argument('project', nargs='?'); pb.add_argument('--reason', default='supervisor_work'); pb.add_argument('--minutes', type=int, default=30); pb.add_argument('--home'); pb.add_argument('--json', action='store_true')
    pi = psub.add_parser('idle'); pi.add_argument('project', nargs='?'); pi.add_argument('--home'); pi.add_argument('--json', action='store_true')
    ps = psub.add_parser('status'); ps.add_argument('project', nargs='?'); ps.add_argument('--home'); ps.add_argument('--json', action='store_true')
    return ap


def _resolve_pm_project_scope(home: Path, project=None):
    if project:
        cfg = config.load_project(home, project)
        return project, cfg['chat_url']
    configs = sorted((home.expanduser() / 'projects').glob('*/config.json'))
    if len(configs) != 1:
        raise ValueError('pm busy/idle/status requires <project> when multiple PMBridge projects are configured')
    inferred = configs[0].parent.name
    cfg = config.load_project(home, inferred)
    return inferred, cfg['chat_url']


def main(argv=None):
    args = build_parser().parse_args(argv)
    home = home_path(getattr(args, 'home', None))
    if args.command == 'bootstrap':
        result = bootstrap(args)
        emit(result, args.json)
        return 0 if result['status'] == 'READY' else 2
    if args.command == 'doctor':
        result = doctor.check(home, args.project)
        emit(result, args.json)
        return 0 if result['status'] == 'READY' else 3
    if args.command == 'run':
        instruction = args.file.read_text(encoding='utf-8') if args.file else args.instruction
        result = run_project(home, args.project, instruction, role=args.role, access=args.access, network=args.network, target=args.target, model=args.model, reasoning_effort=args.reasoning_effort)
        emit(result, args.json)
        return 0
    if args.command == 'smoke':
        instruction = 'PMBridge end-to-end smoke test only. Do not modify files or git state. Reply exactly: PMBRIDGE_SMOKE_OK'
        result = run_project(home, args.project, instruction, role='smoke', access='read', network='none', model=executor.DEFAULT_MODEL, reasoning_effort=executor.DEFAULT_REASONING_EFFORT)
        result['expected_result'] = 'PMBRIDGE_SMOKE_OK'
        emit(result, args.json)
        return 0
    if args.command == 'notify':
        result = notify_job(home, args.job_id, args.status)
        emit(result, args.json)
        return 0 if result['ok'] else 4
    if args.command == 'recovery':
        result = recovery.scan(home)
        try:
            result['events'] = events.drain(home, wait_seconds=15.0, quiet_focused_seconds=12.0, quiet_background_seconds=4.0)
        except Exception as exc:
            result['events'] = {'status':'ERROR','error':type(exc).__name__}
        emit(result, args.json)
        return 0
    if args.command == 'drain':
        result = events.drain(home, wait_seconds=args.wait_seconds, quiet_focused_seconds=args.quiet_focused_seconds, quiet_background_seconds=args.quiet_background_seconds)
        emit(result, args.json)
        return 0
    if args.command == 'rebind':
        result = rebind_project(home, args)
        emit(result, args.json)
        return 0 if result.get('status') == 'READY' else 5
    if args.command == 'handoff':
        result = binding.handoff(home, args.project)
        emit(result, args.json)
        return 0
    if args.command == 'pm':
        try:
            project, scope = _resolve_pm_project_scope(home, args.project)
        except ValueError as exc:
            emit({'status': 'NEEDS_PROJECT', 'error': str(exc)}, args.json)
            return 6
        if args.pm_command == 'busy': result = pm_state.set_busy(home, scope=scope, reason=args.reason, minutes=args.minutes)
        elif args.pm_command == 'idle':
            result = pm_state.set_idle(home, scope=scope)
            try: spawn_event_drain(home)
            except FileNotFoundError: pass
        else: result = pm_state.status(home, scope=scope)
        emit(result, args.json)
        return 0
    if args.command == 'watch':
        code = watcher.attach_job(home, args.job_id) if args.attach else watcher.run_job(home, args.job_id)
        if args.json:
            emit({'status': 'EXITED', 'code': code, 'job_id': args.job_id}, True)
        return code
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
