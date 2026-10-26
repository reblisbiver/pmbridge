#!/bin/zsh
set -uo pipefail
TARGET_URL="${PM_CHAT_URL:?PM_CHAT_URL is required}"
MESSAGE="${1:-PM_BRIDGE_COMPLETE}"
LOG_DIR="${PM_BRIDGE_LOG_DIR:?PM_BRIDGE_LOG_DIR is required}"
LOG_FILE="$LOG_DIR/notify_pm.log"
ERR_FILE="$LOG_DIR/notify_pm_last_error.log"
mkdir -p "$LOG_DIR"
MESSAGE_B64="$(printf '%s' "$MESSAGE" | /usr/bin/base64)"

if osascript - "$TARGET_URL" "$MESSAGE_B64" 2>"$ERR_FILE" <<'APPLESCRIPT'
on run argv
  set targetURL to item 1 of argv
  set msgB64 to item 2 of argv
  tell application "Microsoft Edge"
    set foundTab to missing value
    repeat with w in windows
      repeat with t in tabs of w
        if URL of t is targetURL then
          set foundTab to t
          exit repeat
        end if
      end repeat
      if foundTab is not missing value then exit repeat
    end repeat
    if foundTab is missing value then error "Target ChatGPT PM tab is not open"

    set prepareJS to "(()=>{const decode=(b)=>new TextDecoder().decode(Uint8Array.from(atob(b),c=>c.charCodeAt(0)));const msg=decode('" & msgB64 & "');const c=document.querySelector('[contenteditable=\"true\"][role=\"textbox\"][aria-label=\"Ask ChatGPT\"]');if(!c)return 'NO_COMPOSER';const composerText=(c.innerText||'').trim();const staleBridge=/^(PM_JOB_STATUS |PM_BRIDGE_COMPLETE |CODEX_TURN_COMPLETE |PM_BRIDGE_TIMEOUT )/.test(composerText);if(composerText && composerText!==msg && !staleBridge)return 'BUSY_COMPOSER';if(composerText!==msg){c.focus();c.innerHTML='';const p=document.createElement('p');p.textContent=msg;c.appendChild(p);c.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:msg}));}const b=document.querySelector('button[aria-label=\"Send\"]');if(!b||b.disabled)return 'NO_SEND';const f=b.closest('form');if(f&&typeof f.requestSubmit==='function')f.requestSubmit(b);else b.click();return 'SUBMITTED';})()"
    set verifyJS to "(()=>{const c=document.querySelector('[contenteditable=\"true\"][role=\"textbox\"][aria-label=\"Ask ChatGPT\"]');if(!c)return 'NO_COMPOSER';const composerText=(c.innerText||'').trim();const msg=new TextDecoder().decode(Uint8Array.from(atob('" & msgB64 & "'),x=>x.charCodeAt(0)));if(composerText==='')return 'DELIVERED';if(composerText===msg)return 'STILL_PENDING';return 'BUSY_COMPOSER';})()"
    set retryJS to "(()=>{const b=document.querySelector('button[aria-label=\"Send\"]');if(!b||b.disabled)return 'NO_SEND';const f=b.closest('form');if(f&&typeof f.requestSubmit==='function')f.requestSubmit(b);else b.click();return 'RESUBMITTED';})()"

    set finalState to "NOT_READY"
    repeat with attempt from 1 to 120
      set prepState to execute foundTab javascript prepareJS
      if prepState is "BUSY_COMPOSER" then
        delay 0.5
      else if prepState is "SUBMITTED" then
        delay 2.0
        set finalState to execute foundTab javascript verifyJS
        if finalState is "DELIVERED" then exit repeat
        if finalState is "STILL_PENDING" then
          repeat with sendAttempt from 1 to 1
            set retryState to execute foundTab javascript retryJS
            delay 0.4
            set finalState to execute foundTab javascript verifyJS
            if finalState is "DELIVERED" then exit repeat
            if finalState is not "STILL_PENDING" then exit repeat
          end repeat
          if finalState is "DELIVERED" then exit repeat
        end if
        delay 0.5
      else
        set finalState to prepState
        delay 0.5
      end if
    end repeat
    if finalState is not "DELIVERED" then error "DOM delivery not confirmed: " & finalState
  end tell
end run
APPLESCRIPT
then
  rm -f "$ERR_FILE"
  printf '%s SUCCESS target=%s
' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$TARGET_URL" >> "$LOG_FILE"
  exit 0
else
  rc=$?
  printf '%s FAILURE rc=%s target=%s
' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$rc" "$TARGET_URL" >> "$LOG_FILE"
  exit "$rc"
fi
