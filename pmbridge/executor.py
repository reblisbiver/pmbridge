import shutil
from pathlib import Path

APP_CODEX = Path('/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex')


def find_codex() -> Path:
    if APP_CODEX.exists():
        return APP_CODEX
    found = shutil.which('codex')
    if found:
        return Path(found)
    raise FileNotFoundError('Codex CLI not found')


def build_codex_command(repo: Path, result_file: Path, codex: Path = None):
    binary = codex or find_codex()
    return [str(binary), 'exec', '-C', str(repo), '--approve-for-me', '-o', str(result_file), '-']
