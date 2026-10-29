#!/usr/bin/env python3
"""Non-invasive context helpers for legacy PM bridges.

This file does not dispatch, watch, notify, mutate jobs, or alter callback routing.
It only indexes existing evidence, stores PM-controlled ledger JSON, reports
objective byte/count metrics, and adapts those legacy sources into a four-layer
takeover view. Raw evidence is never removed.
"""
import argparse, json, os
from collections import Counter
from datetime import datetime
from pathlib import Path

PREVIEW_CHARS=12000


def meta(path):
    if not path: return {'path':None,'exists':False,'bytes':0}
    p=Path(path)
    try: return {'path':str(p),'exists':True,'bytes':p.stat().st_size}
    except OSError: return {'path':str(p),'exists':False,'bytes':0}


def preview(text, full=False):
    if text is None: return {'text':None,'truncated':False}
    if full or len(text)<=PREVIEW_CHARS: return {'text':text,'truncated':False}
    return {'text':text[:PREVIEW_CHARS],'truncated':True,'total_chars':len(text)}


def io_final_message(log_path):
    if not log_path or not Path(log_path).exists(): return None
    final=None
    with Path(log_path).open(encoding='utf-8',errors='replace') as fh:
        for line in fh:
            try:o=json.loads(line)
            except Exception: continue
            if o.get('type')=='item.completed':
                item=o.get('item') or {}
                if item.get('type')=='agent_message': final=item.get('text')
    return final


def inspect(root, ident, full=False):
    bridge=root/'state'/'bridges'/f'{ident}.json'
    jobp=root/'jobs'/f'{ident}.json'
    if bridge.exists():
        data=json.loads(bridge.read_text())
        log=data.get('run_log')
        final=io_final_message(log)
        return {
            'status':'READY','kind':'legacy-role-bridge',
            'job':{k:data.get(k) for k in ('bridge_id','role','status','target','mode','network','thread_id','turn_id','runner','runner_pid','created_at','completed_at') if k in data},
            'result':{**preview(final,full), 'source':'final_agent_message_in_jsonl'},
            'raw_evidence':{'manifest':meta(bridge),'log':meta(log)},
        }
    if jobp.exists():
        data=json.loads(jobp.read_text())
        rp=data.get('result_file'); text=None
        if rp and Path(rp).exists(): text=Path(rp).read_text(encoding='utf-8',errors='replace')
        keys=('job_id','project','status','pid','watcher_pid','started_at','finished_at','exit_code')
        return {
            'status':'READY','kind':'legacy-job',
            'job':{k:data.get(k) for k in keys if k in data},
            'result':{**meta(rp),**preview(text,full)},
            'raw_evidence':{'manifest':meta(jobp),'prompt':meta(data.get('prompt_file')),'log':meta(data.get('output_file')),'result':meta(rp)},
        }
    raise FileNotFoundError(f'no legacy bridge/job record for {ident}')


def ledger_path(root): return root/'state'/'pm-ledger.json'
def ledger_load(root):
    p=ledger_path(root)
    return json.loads(p.read_text()) if p.exists() else None

def ledger_write(root,data):
    p=ledger_path(root); p.parent.mkdir(parents=True,exist_ok=True)
    old=ledger_load(root); version=(int(old.get('version',0))+1) if isinstance(old,dict) else 1
    payload={'version':version,'updated_at':datetime.now().astimezone().isoformat(timespec='seconds'),'data':data}
    tmp=p.with_suffix('.json.tmp'); tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n'); os.replace(tmp,p); return payload

def ledger_patch(root,patch):
    old=ledger_load(root); data=old.get('data',{}) if isinstance(old,dict) else {}
    if not isinstance(data,dict): raise ValueError('ledger patch requires JSON-object ledger data; use replace otherwise')
    out=dict(data); out.update(patch); return ledger_write(root,out)


def size(p):
    try:return Path(p).stat().st_size if p else 0
    except OSError:return 0


def context(root):
    bridges=root/'state'/'bridges'; jobs=root/'jobs'
    if bridges.exists() and any(bridges.glob('*.json')):
        records=[]
        for p in bridges.glob('*.json'):
            try: records.append(json.loads(p.read_text()))
            except Exception: pass
        return {'status':'READY','kind':'legacy-role-bridge','jobs':len(records),'jobs_by_status':dict(Counter(r.get('status') for r in records)),'jobs_by_role':dict(Counter(r.get('role') for r in records if r.get('role'))),'raw_evidence_bytes':sum(size(r.get('run_log')) for r in records),'ledger':ledger_load(root)}
    records=[]
    if jobs.exists():
        for p in jobs.glob('*.json'):
            if p.name.endswith('.lock'): continue
            try: records.append(json.loads(p.read_text()))
            except Exception: pass
    return {'status':'READY','kind':'legacy-job','jobs':len(records),'jobs_by_status':dict(Counter(r.get('status') for r in records)),'raw_evidence_bytes':sum(size(r.get('output_file')) for r in records),'result_bytes':sum(size(r.get('result_file')) for r in records),'ledger':ledger_load(root)}


def takeover(root):
    """Adapt legacy read helpers without pretending to own generic runtime state."""
    metrics = context(root)
    execution = {key: value for key, value in metrics.items() if key not in {'status', 'kind', 'ledger'}}
    return {
        'status': 'READY',
        'project': {
            'name': root.name,
            'root': str(root),
            'working_state': metrics.get('ledger'),
        },
        'supervision': {
            'role': 'product_manager',
            'charter': {'path': 'docs/pm-operating-charter.md', 'read_first': True},
            'continuity': {'canonical_view': 'takeover', 'adapter': 'compat.pm_context'},
        },
        'execution': {'adapter': 'compat.pm_context', 'kind': metrics.get('kind'), **execution},
        'runtime': {
            'adapter': 'compat.pm_context',
            'capabilities': {
                'binding': False,
                'callbacks': False,
                'edge_delivery': False,
                'watchers': False,
                'recovery': False,
            },
        },
    }


def get_data(args):
    raw=args.file.read_text(encoding='utf-8') if args.file else args.data
    return json.loads(raw)


def main(argv=None):
    ap=argparse.ArgumentParser(prog='pm-context')
    ap.add_argument('--bridge-root',type=Path,default=Path(__file__).resolve().parent)
    sub=ap.add_subparsers(dest='command',required=True)
    i=sub.add_parser('inspect'); i.add_argument('id'); i.add_argument('--full-result',action='store_true')
    sub.add_parser('context')
    sub.add_parser('takeover')
    lg=sub.add_parser('ledger'); ls=lg.add_subparsers(dest='ledger_command',required=True)
    ls.add_parser('show')
    for n in ('replace','patch'):
        x=ls.add_parser(n); g=x.add_mutually_exclusive_group(required=True); g.add_argument('--data'); g.add_argument('--file',type=Path)
    a=ap.parse_args(argv); root=a.bridge_root.expanduser().resolve()
    if a.command=='inspect': out=inspect(root,a.id,a.full_result)
    elif a.command=='context': out=context(root)
    elif a.command=='takeover': out=takeover(root)
    elif a.ledger_command=='show': out=ledger_load(root) or {'status':'EMPTY','data':None}
    elif a.ledger_command=='replace': out=ledger_write(root,get_data(a))
    else:
        d=get_data(a)
        if not isinstance(d,dict): raise ValueError('ledger patch data must be a JSON object')
        out=ledger_patch(root,d)
    print(json.dumps(out,ensure_ascii=False,indent=2)); return 0

if __name__=='__main__': raise SystemExit(main())
