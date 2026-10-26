import subprocess
from pathlib import Path


def repo_root(path: Path):
    proc = subprocess.run(
        ['git', '-C', str(path), 'rev-parse', '--show-toplevel'],
        text=True, capture_output=True, check=False,
    )
    if proc.returncode != 0:
        return None
    return Path(proc.stdout.strip()).resolve()


def ensure_repo(path: Path, init_repo: bool = False):
    path = path.expanduser().resolve()
    root = repo_root(path)
    if root:
        return {'status': 'READY', 'repo': str(root), 'created': False}
    if not init_repo:
        return {'status': 'NEEDS_REPO_CONFIRMATION', 'path': str(path)}
    proc = subprocess.run(
        ['git', '-C', str(path), 'init', '-b', 'main'],
        text=True, capture_output=True, check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip())
    return {'status': 'READY', 'repo': str(path), 'created': True}
