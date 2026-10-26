import shutil
from pathlib import Path

from . import codex_profiles

APP_CODEX = Path('/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex')
DEFAULT_MODEL = 'gpt-5.6-luna'
DEFAULT_REASONING_EFFORT = 'xhigh'


def find_codex() -> Path:
    if APP_CODEX.exists():
        return APP_CODEX
    found = shutil.which('codex')
    if found:
        return Path(found)
    raise FileNotFoundError('Codex CLI not found')


def build_codex_command(
    repo: Path,
    result_file: Path,
    access: str = 'write',
    network: str = 'none',
    model: str = DEFAULT_MODEL,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
    codex: Path = None,
):
    if access not in {'read', 'write'}:
        raise ValueError(f'unsupported access mode: {access}')
    if network not in {'none', 'local'}:
        raise ValueError(f'unsupported network mode: {network}')
    binary = codex or find_codex()
    cmd = [
        str(binary), 'exec',
        '-m', model,
        '-c', f'model_reasoning_effort="{reasoning_effort}"',
    ]
    profile = codex_profiles.profile_name(access, network)
    if profile:
        cmd += ['-p', profile]
    else:
        cmd += ['-s', 'read-only' if access == 'read' else 'workspace-write']
    cmd += ['-C', str(repo)]
    if access == 'write' and network == 'none':
        cmd.append('--approve-for-me')
    cmd += ['-o', str(result_file), '-']
    return cmd
