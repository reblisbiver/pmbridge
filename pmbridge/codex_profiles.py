import os
from pathlib import Path

READ_LOCAL = 'pmbridge-read-local'
WRITE_LOCAL = 'pmbridge-write-local'
READ_INTERNET = 'pmbridge-read-internet'
WRITE_INTERNET = 'pmbridge-write-internet'


def codex_home(path=None) -> Path:
    return Path(path or os.environ.get('CODEX_HOME', '~/.codex')).expanduser().resolve()


def _render(name: str, parent: str, mode: str, domains=None) -> str:
    if domains is None:
        domains = ['localhost', '127.0.0.1', '::1']
    domain_lines = '\n'.join(f'"{domain}" = "allow"' for domain in domains)
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
{domain_lines}
'''


def install(path=None) -> dict:
    root = codex_home(path)
    root.mkdir(parents=True, exist_ok=True)
    profiles = {
        'read-local': (READ_LOCAL, ':read-only', 'full', ['localhost', '127.0.0.1', '::1']),
        'write-local': (WRITE_LOCAL, ':workspace', 'full', ['localhost', '127.0.0.1', '::1']),
        'read-internet': (READ_INTERNET, ':read-only', 'full', ['*']),
        'write-internet': (WRITE_INTERNET, ':workspace', 'full', ['*']),
    }
    result = {}
    for key, (name, parent, mode, domains) in profiles.items():
        target = root / f'{name}.config.toml'
        target.write_text(_render(name, parent, mode, domains), encoding='utf-8')
        result[key] = str(target)
    return result


def profile_name(access: str, network: str):
    if network in {None, 'none'}:
        return None
    if network not in {'local', 'internet'}:
        raise ValueError(f'unsupported network mode: {network}')
    if access not in {'read', 'write'}:
        raise ValueError(f'network={network} requires explicit access read|write because the network profile also defines filesystem policy')
    if network == 'local':
        return READ_LOCAL if access == 'read' else WRITE_LOCAL
    return READ_INTERNET if access == 'read' else WRITE_INTERNET
