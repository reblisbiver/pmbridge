import base64
import json
import os
import subprocess
import time
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


def find_chat_by_texts(markers, attempts: int = 1, delay: float = 0.25, timeout: float = 2.0) -> dict:
    markers = [str(x).strip() for x in markers if str(x).strip()]
    if not markers:
        return {'status': 'NEEDS_CHAT_BINDING'}
    payload_b64 = base64.b64encode(json.dumps(markers, ensure_ascii=False).encode('utf-8')).decode('ascii')
    script = r'''on run argv
  set payloadB64 to item 1 of argv
  set matches to {}
  tell application "Microsoft Edge"
    repeat with w in windows
      repeat with t in tabs of w
        set u to URL of t
        if u starts with "https://chatgpt.com/c/" then
          try
            set js to "(()=>{const xs=JSON.parse(new TextDecoder().decode(Uint8Array.from(atob('" & payloadB64 & "'),c=>c.charCodeAt(0))));const body=(document.body&&document.body.innerText)||'';return xs.every(x=>body.includes(x))?'MATCH':'NO';})()"
            set r to execute t javascript js
            if r is "MATCH" then set end of matches to u
          end try
        end if
      end repeat
    end repeat
  end tell
  set AppleScript's text item delimiters to linefeed
  return matches as text
end run'''
    last = {'status': 'CHAT_BINDING_NOT_FOUND'}
    total = max(1, attempts)
    for attempt in range(total):
        try:
            proc = subprocess.run(
                ['osascript', '-', payload_b64], input=script, text=True,
                capture_output=True, check=False, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            last = {'status': 'CHAT_BINDING_TIMEOUT'}
        else:
            if proc.returncode != 0:
                last = {'status': 'CHAT_BINDING_ERROR', 'error': (proc.stderr or proc.stdout or '').strip()}
            else:
                urls = [line.strip() for line in (proc.stdout or '').splitlines() if line.strip()]
                urls = list(dict.fromkeys(urls))
                if len(urls) == 1:
                    return {'status': 'FOUND', 'url': urls[0]}
                if len(urls) > 1:
                    return {'status': 'AMBIGUOUS_CHAT_BINDING', 'matches': urls}
                last = {'status': 'CHAT_BINDING_NOT_FOUND'}
        if attempt < total - 1:
            time.sleep(delay)
    return last


def find_chat_by_token(token: str, attempts: int = 1, delay: float = 0.25) -> dict:
    return find_chat_by_texts([token], attempts=attempts, delay=delay)


def ui_state(chat_url: str, timeout: float = 4.0) -> dict:
    script = r'''on run argv
  set targetURL to item 1 of argv
  tell application "Microsoft Edge"
    repeat with w in windows
      repeat with t in tabs of w
        if URL of t is targetURL then
          try
            set js to "(()=>{const c=document.querySelector('[contenteditable=\\\"true\\\"][role=\\\"textbox\\\"]');const composer=(c?.innerText||'').trim();const stop=[...document.querySelectorAll('button')].some(b=>{const a=(b.getAttribute('aria-label')||'').trim();return a==='Stop'||/^Stop (generating|streaming|responding)$/i.test(a)||b.dataset?.testid==='stop-button'});const main=document.querySelector('main');const tail=(main?.innerText||document.body.innerText||'').slice(-500);const signature=[tail,composer,stop?'1':'0'].join('|');return JSON.stringify({reachable:true,composer_nonempty:!!composer,generating:stop,signature,visibility:document.visibilityState,focused:document.hasFocus()});})()"
            return execute t javascript js
          on error errMsg
            return "{\"reachable\":false,\"reason\":\"js_error\"}"
          end try
        end if
      end repeat
    end repeat
  end tell
  return "{\"reachable\":false,\"reason\":\"tab_missing\"}"
end run'''
    try:
        proc = subprocess.run(['osascript', '-', chat_url], input=script, text=True, capture_output=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {'reachable': False, 'reason': 'timeout'}
    text = (proc.stdout or '').strip()
    try:
        return json.loads(text)
    except Exception:
        return {'reachable': False, 'reason': 'invalid_probe'}
