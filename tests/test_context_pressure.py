import tempfile, unittest, json, time
from pathlib import Path
from pmbridge import context_pressure, config, state

class ContextPressureTests(unittest.TestCase):
    def test_report_scopes_project_and_measures_without_threshold_policy(self):
        with tempfile.TemporaryDirectory() as td:
            h=Path(td); r=h/'r'; r.mkdir(); config.save_project(h,{'version':1,'name':'p','repo':str(r),'chat_url':'https://chatgpt.com/c/x','binding_version':1,'binding_updated_at':'2026-01-01T00:00:00+00:00'})
            (h/'jobs').mkdir()
            for jid,proj,log,result in [('a','p','x'*100,'ok'),('b','other','z'*900,'no')]:
                lp=h/'jobs'/f'{jid}.log'; rp=h/'jobs'/f'{jid}.result.txt'; lp.write_text(log); rp.write_text(result)
                state.write_job(h/'jobs'/f'{jid}.json',{'job_id':jid,'project':proj,'status':'completed','started_at':time.time(),'output_file':str(lp),'result_file':str(rp)})
            d=h/'events'/'delivered'; d.mkdir(parents=True); (d/'e.json').write_text(json.dumps({'project':'p','job_id':'a','status':'completed','delivered_at':time.time()}))
            out=context_pressure.report(h,'p')
            self.assertEqual(out['jobs'],1); self.assertEqual(out['callbacks'],1); self.assertEqual(out['raw_evidence_bytes'],100); self.assertEqual(out['result_bytes'],2)
            self.assertNotIn('pressure_level',out); self.assertNotIn('recommendation',out)
