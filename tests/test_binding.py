import json
import tempfile
import unittest
from pathlib import Path

from pmbridge import binding, config, state


class BindingTests(unittest.TestCase):
    def setup_project(self, home):
        repo = home/'repo'; repo.mkdir()
        cfg = {'version':1,'name':'demo','repo':str(repo),'chat_url':'https://chatgpt.com/c/old','binding_version':1,'stall_seconds':1200}
        config.save_project(home, cfg)
        return cfg

    def test_rebind_updates_only_active_chat_and_records_history(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td); self.setup_project(home)
            jobs=home/'jobs'; jobs.mkdir()
            state.write_job(jobs/'j.json', {'job_id':'j','project':'demo','status':'running','pid':123,'watcher_pid':456})
            before=state.load_job(jobs/'j.json').copy()
            out=binding.rebind(home,'demo','https://chatgpt.com/c/new',source='test')
            cfg=config.load_project(home,'demo')
            self.assertEqual(cfg['chat_url'],'https://chatgpt.com/c/new')
            self.assertEqual(cfg['binding_version'],2)
            self.assertEqual(state.load_job(jobs/'j.json'),before)
            history=(home/'projects'/'demo'/'bindings'/'history.jsonl').read_text().splitlines()
            self.assertEqual(len(history),1)
            entry=json.loads(history[0])
            self.assertEqual(entry['previous_chat_url'],'https://chatgpt.com/c/old')
            self.assertEqual(entry['new_chat_url'],'https://chatgpt.com/c/new')
            self.assertEqual(out['binding_version'],2)

    def test_handoff_summarizes_jobs_and_pending_without_prompt_contents(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td); self.setup_project(home)
            (home/'jobs').mkdir()
            state.write_job(home/'jobs'/'a.json', {'job_id':'a','project':'demo','status':'running','role':'qa','target':'abc','access':'read','network':'local','model':'gpt-5.6-luna','reasoning_effort':'xhigh'})
            state.write_job(home/'jobs'/'b.json', {'job_id':'b','project':'demo','status':'completed','role':'impl','target':None,'access':'write','network':'none','model':'gpt-5.6-luna','reasoning_effort':'xhigh','finished_at':2})
            p=home/'events'/'pending'; p.mkdir(parents=True)
            (p/'1.json').write_text(json.dumps({'event_id':'e1','job_id':'a','project':'demo','status':'stalled'}))
            snap=binding.handoff(home,'demo')
            self.assertEqual(snap['project'],'demo')
            self.assertEqual(snap['active_binding']['url'],'https://chatgpt.com/c/old')
            self.assertEqual([j['job_id'] for j in snap['active_jobs']],['a'])
            self.assertEqual(snap['pending_events'][0]['job_id'],'a')
            self.assertNotIn('prompt_file', snap['active_jobs'][0])
            self.assertEqual(snap['recent_jobs'][0]['job_id'],'b')

if __name__ == '__main__': unittest.main()
