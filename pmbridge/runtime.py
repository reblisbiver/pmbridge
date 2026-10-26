import shutil
import stat
from pathlib import Path


def install(home: Path) -> dict:
    home = home.expanduser().resolve()
    source_pkg = Path(__file__).resolve().parent
    runtime_root = home / 'runtime'
    target_pkg = runtime_root / 'pmbridge'
    bin_dir = home / 'bin'
    logs_dir = home / 'logs'
    runtime_root.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    if target_pkg.exists():
        shutil.rmtree(target_pkg)
    shutil.copytree(source_pkg, target_pkg)
    script = target_pkg / 'edge_notify.sh'
    if script.exists():
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
    wrapper = bin_dir / 'pmbridge'
    wrapper.write_text(
        '#!/bin/zsh\n'
        f'export PYTHONPATH="{runtime_root}${{PYTHONPATH:+:$PYTHONPATH}}"\n'
        'exec /usr/bin/python3 -m pmbridge.cli "$@"\n',
        encoding='utf-8',
    )
    wrapper.chmod(0o755)
    return {'status': 'READY', 'runtime': str(runtime_root), 'command': str(wrapper)}
