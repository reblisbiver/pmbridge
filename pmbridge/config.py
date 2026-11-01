import json
from pathlib import Path


def default_project_name(repo: Path) -> str:
    return repo.resolve().name


def projects_dir(home: Path) -> Path:
    return home.expanduser() / 'projects'


def save_project(home: Path, cfg: dict) -> Path:
    root = projects_dir(home) / cfg['name']
    root.mkdir(parents=True, exist_ok=True)
    path = root / 'config.json'
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)
    return path


def load_project(home: Path, name: str) -> dict:
    path = projects_dir(home) / name / 'config.json'
    return json.loads(path.read_text(encoding='utf-8'))


def list_projects(home: Path) -> list:
    root = projects_dir(home)
    if not root.exists():
        return []
    projects = []
    for path in sorted(root.glob('*/config.json')):
        try:
            cfg = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            continue
        name = cfg.get('name') or path.parent.name
        repo = cfg.get('repo')
        if not repo:
            continue
        projects.append({
            'name': name,
            'repo': repo,
            'repo_exists': Path(repo).expanduser().exists(),
            'chat_url': cfg.get('chat_url'),
            'binding_version': cfg.get('binding_version'),
            'binding_guarded': bool(cfg.get('binding_guarded', False)),
        })
    return sorted(projects, key=lambda item: item['name'])
