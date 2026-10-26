import shutil
from pathlib import Path

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
    model: str = DEFAULT_MODEL,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
    codex: Path = None,
):
    if access not in {'read', 'write'}:
        raise ValueError(f'unsupported access mode: {access}')
    binary = codex or find_codex()
    cmd = [
        str(binary), 'exec',
        '-m', model,
        '-c', f'model_reasoning_effort="{reasoning_effort}"',
        '-s', 'read-only' if access == 'read' else 'workspace-write',
        '-C', str(repo),
    ]
    if access == 'write':
        cmd.append('--approve-for-me')
    cmd += ['-o', str(result_file), '-']
    return cmd
