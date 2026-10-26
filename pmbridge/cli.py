import argparse
import json
import os
import subprocess
from pathlib import Path

from . import config, doctor, gitops, jobs, launchd, recovery, runtime, state, transport_edge, watcher


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


def run_project(home: Path, project: str, instruction: str) -> dict:
    cfg = config.load_project(home, project)
    job = jobs.create_job(home, project, Path(cfg['repo']), instruction, int(cfg.get('stall_seconds', 1200)))
    proc = spawn_watcher(home, job['job_id'])
    state.safe_transition(home/'jobs'/f"{job['job_id']}.json", watcher_pid=proc.pid)
    return {'status': 'STARTED', 'project': project, 'job_id': job['job_id'], 'watcher_pid': proc.pid}


def notify_job(home: Path, job_id: str, status_text: str) -> dict:
    job = state.load_job(home/'jobs'/f'{job_id}.json')
    cfg = config.load_project(home, job['project'])
    return transport_edge.send(cfg['chat_url'], f'PM_JOB_STATUS {job_id} {status_text}', home)


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
    return ap


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
        result = run_project(home, args.project, instruction)
        emit(result, args.json)
        return 0
    if args.command == 'smoke':
        instruction = 'PMBridge end-to-end smoke test only. Do not modify files or git state. Reply exactly: PMBRIDGE_SMOKE_OK'
        result = run_project(home, args.project, instruction)
        result['expected_result'] = 'PMBRIDGE_SMOKE_OK'
        emit(result, args.json)
        return 0
    if args.command == 'notify':
        result = notify_job(home, args.job_id, args.status)
        emit(result, args.json)
        return 0 if result['ok'] else 4
    if args.command == 'recovery':
        result = recovery.scan(home)
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
