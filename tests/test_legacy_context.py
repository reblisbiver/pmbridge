import json, subprocess, tempfile, unittest
from pathlib import Path

SCRIPT=Path(__file__).parents[1]/'compat'/'pm_context.py'
class LegacyContextTests(unittest.TestCase):
    def invoke(self,root,*args):
        p=subprocess.run(['python3',str(SCRIPT),'--bridge-root',str(root),*args],capture_output=True,text=True,check=True)
        return json.loads(p.stdout)
    def test_io_role_log_extracts_only_final_agent_message(self):
        with tempfile.TemporaryDirectory() as td:
            r=Path(td); (r/'state/bridges').mkdir(parents=True); (r/'logs').mkdir()
            lp=r/'logs/run.jsonl'; lp.write_text(json.dumps({'type':'item.completed','item':{'type':'command_execution','aggregated_output':'HUGE_SECRET'}})+'\n'+json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'ACCEPT compact'}})+'\n')
            (r/'state/bridges/b.json').write_text(json.dumps({'bridge_id':'b','role':'qa','status':'completed','run_log':str(lp)}))
            out=self.invoke(r,'inspect','b')
            self.assertEqual(out['result']['text'],'ACCEPT compact'); self.assertNotIn('HUGE_SECRET',json.dumps(out)); self.assertGreater(out['raw_evidence']['log']['bytes'],0)
    def test_legacy_job_and_ledger_context(self):
        with tempfile.TemporaryDirectory() as td:
            r=Path(td); (r/'jobs').mkdir(); (r/'state').mkdir(); lp=r/'jobs/j.log'; rp=r/'jobs/j.result.txt'; lp.write_text('raw'*100); rp.write_text('final')
            (r/'jobs/j.json').write_text(json.dumps({'job_id':'j','project':'p','status':'completed','output_file':str(lp),'result_file':str(rp)}))
            out=self.invoke(r,'inspect','j'); self.assertEqual(out['result']['text'],'final')
            self.invoke(r,'ledger','replace','--data','{"goal":"x"}')
            ctx=self.invoke(r,'context'); self.assertEqual(ctx['jobs'],1); self.assertEqual(ctx['ledger']['data']['goal'],'x')

            takeover = self.invoke(r, 'takeover')
            self.assertEqual(set(takeover), {'status','project','supervision','execution','runtime'})
            self.assertEqual(takeover['project']['name'], r.name)
            self.assertEqual(takeover['project']['working_state']['data']['goal'], 'x')
            self.assertEqual(takeover['execution']['kind'], 'legacy-job')
            self.assertFalse(takeover['runtime']['capabilities']['binding'])
            self.assertFalse(takeover['runtime']['capabilities']['watchers'])
