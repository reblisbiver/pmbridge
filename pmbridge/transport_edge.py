import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).with_name('edge_notify.sh')


def send(chat_url: str, message: str, home: Path) -> dict:
    env = os.environ.copy()
    env['PM_CHAT_URL'] = chat_url
    env['PM_BRIDGE_LOG_DIR'] = str(home.expanduser() / 'logs')
    proc = subprocess.run(
        [str(SCRIPT), message],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    return {
        'ok': proc.returncode == 0,
        'returncode': proc.returncode,
        'error': (proc.stderr or proc.stdout or '').strip(),
    }


def probe(chat_url: str) -> dict:
    script = r'''on run argv
  set targetURL to item 1 of argv
  tell application "Microsoft Edge"
    repeat with w in windows
      repeat with t in tabs of w
        if URL of t is targetURL then
          try
            set resultText to execute t javascript "String(document.title || 'OK')"
            return "OK:" & resultText
          on error errMsg
            return "JS_ERROR:" & errMsg
          end try
        end if
      end repeat
    end repeat
  end tell
  return "TAB_MISSING"
end run
'''
    proc = subprocess.run(['osascript', '-', chat_url], input=script, text=True, capture_output=True, check=False)
    text = (proc.stdout or proc.stderr or '').strip()
    return {'ok': proc.returncode == 0 and text.startswith('OK:'), 'detail': text or f'osascript rc={proc.returncode}'}


def current_chat_url():
    script = '''tell application "Microsoft Edge"
  if (count of windows) is 0 then return ""
  set u to URL of active tab of front window
  return u
end tell'''
    proc = subprocess.run(['osascript', '-e', script], text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        return None
    url = (proc.stdout or '').strip()
    if url.startswith('https://chatgpt.com/c/'):
        return url
    return None
