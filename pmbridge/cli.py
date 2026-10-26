import argparse
import json
import os
from pathlib import Path

from . import config, gitops


def emit(payload, as_json):
    if as_json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(payload)


def bootstrap(args):
    repo_result = gitops.ensure_repo(Path(args.repo), init_repo=args.init_repo)
    if repo_result['status'] != 'READY':
        return repo_result
    repo = Path(repo_result['repo'])
    name = args.name or config.default_project_name(repo)
    cfg = {
        'version': 1,
        'name': name,
        'repo': str(repo),
        'chat_url': args.chat_url,
        'stall_seconds': args.stall_seconds,
    }
    home = Path(args.home or os.environ.get('PMBRIDGE_HOME', '~/.pmbridge')).expanduser()
    path = config.save_project(home, cfg)
    return {'status': 'READY', 'project': name, 'config': str(path), 'repo_created': repo_result['created']}


def build_parser():
    ap = argparse.ArgumentParser(prog='pmbridge')
    sub = ap.add_subparsers(dest='command', required=True)
    bp = sub.add_parser('bootstrap')
    bp.add_argument('--repo', required=True)
    bp.add_argument('--chat-url', required=True)
    bp.add_argument('--name')
    bp.add_argument('--stall-seconds', type=int, default=1200)
    bp.add_argument('--init-repo', action='store_true')
    bp.add_argument('--home')
    bp.add_argument('--json', action='store_true')
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.command == 'bootstrap':
        result = bootstrap(args)
        emit(result, args.json)
        return 0 if result['status'] == 'READY' else 2
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
