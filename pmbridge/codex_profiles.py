import os
from pathlib import Path

READ_LOCAL = 'pmbridge-read-local'
WRITE_LOCAL = 'pmbridge-write-local'


def codex_home(path=None) -> Path:
    return Path(path or os.environ.get('CODEX_HOME', '~/.codex')).expanduser().resolve()


def _render(name: str, parent: str, mode: str) -> str:
    return f'''default_permissions = "{name}"

[features]
network_proxy = true

[permissions.{name}]
extends = "{parent}"

[permissions.{name}.network]
enabled = true
mode = "{mode}"
allow_local_binding = true

[permissions.{name}.network.domains]
"localhost" = "allow"
"127.0.0.1" = "allow"
"::1" = "allow"
'''


def install(path=None) -> dict:
    root = codex_home(path)
    root.mkdir(parents=True, exist_ok=True)
    profiles = {
        'read-local': (READ_LOCAL, ':read-only', 'full'),
        'write-local': (WRITE_LOCAL, ':workspace', 'full'),
    }
    result = {}
    for key, (name, parent, mode) in profiles.items():
        target = root / f'{name}.config.toml'
        target.write_text(_render(name, parent, mode), encoding='utf-8')
        result[key] = str(target)
    return result


def profile_name(access: str, network: str):
    if network == 'none':
        return None
    if network != 'local':
        raise ValueError(f'unsupported network mode: {network}')
    if access == 'read':
        return READ_LOCAL
    if access == 'write':
        return WRITE_LOCAL
    raise ValueError(f'unsupported access mode: {access}')
