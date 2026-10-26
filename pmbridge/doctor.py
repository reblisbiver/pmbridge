import os
import subprocess
from pathlib import Path

from . import codex_profiles, config, executor, transport_edge

EDGE_APP = Path('/Applications/Microsoft Edge.app')


def supervisor_loaded() -> bool:
    proc = subprocess.run(
        ['launchctl', 'print', f'gui/{os.getuid()}/com.pmbridge.recovery'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    return proc.returncode == 0


def check(home: Path, project: str, edge_exists=None, launchd_loaded=None, codex_home=None) -> dict:
    home = home.expanduser()
    checks = []
    try:
        cfg = config.load_project(home, project)
        checks.append({'name': 'config', 'ok': True, 'detail': str(home/'projects'/project/'config.json')})
    except Exception as exc:
        return {'status': 'NOT_READY', 'checks': [{'name': 'config', 'ok': False, 'detail': str(exc)}]}
    repo = Path(cfg['repo'])
    checks.append({'name': 'repo', 'ok': repo.exists() and (repo/'.git').exists() or (repo/'.git').is_file(), 'detail': str(repo)})
    try:
        codex = executor.find_codex()
        checks.append({'name': 'codex', 'ok': True, 'detail': str(codex)})
    except Exception as exc:
        checks.append({'name': 'codex', 'ok': False, 'detail': str(exc)})
    codex_root = codex_profiles.codex_home(codex_home)
    for profile in (codex_profiles.READ_LOCAL, codex_profiles.WRITE_LOCAL):
        profile_path = codex_root / f'{profile}.config.toml'
        checks.append({'name': f'codex_profile:{profile}', 'ok': profile_path.exists(), 'detail': str(profile_path)})
    edge_ok = EDGE_APP.exists() if edge_exists is None else edge_exists
    checks.append({'name': 'edge', 'ok': bool(edge_ok), 'detail': str(EDGE_APP)})
    probe = transport_edge.probe(cfg['chat_url'])
    checks.append({'name': 'chat_tab', 'ok': bool(probe['ok']), 'detail': probe['detail']})
    wrapper = home/'bin'/'pmbridge'
    checks.append({'name': 'runtime', 'ok': wrapper.exists(), 'detail': str(wrapper)})
    supervisor = supervisor_loaded() if launchd_loaded is None else launchd_loaded
    checks.append({'name': 'supervisor', 'ok': bool(supervisor), 'detail': 'com.pmbridge.recovery'})
    return {'status': 'READY' if all(c['ok'] for c in checks) else 'NOT_READY', 'project': project, 'checks': checks}
