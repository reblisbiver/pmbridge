import json
import tempfile
import unittest
from pathlib import Path

from pmbridge import binding, config, ledger, pm_state, state


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
            self.assertEqual(snap['execution_defaults']['model'],'gpt-5.6-luna')
            self.assertEqual(snap['execution_defaults']['reasoning_effort'],'xhigh')
            self.assertEqual(snap['active_binding']['url'],'https://chatgpt.com/c/old')
            self.assertEqual([j['job_id'] for j in snap['active_jobs']],['a'])
            self.assertEqual(snap['pending_events'][0]['job_id'],'a')
            self.assertNotIn('prompt_file', snap['active_jobs'][0])
            self.assertEqual(snap['recent_jobs'][0]['job_id'],'b')

            self.assertEqual(snap['takeover']['execution']['active_jobs'][0]['job_id'], 'a')
            self.assertEqual(snap['takeover']['project']['name'], 'demo')

    def test_takeover_separates_four_layers_without_creating_state(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td); self.setup_project(home)
            ledger.replace(home, 'demo', {'goal':'ship', 'decisions':['keep-json'], 'focus':'handoff'})
            (home/'jobs').mkdir()
            prompt = home/'jobs'/'a.prompt.txt'; result = home/'jobs'/'a.result.txt'
            prompt.write_text('PRIVATE PROMPT')
            result.write_text('PRIVATE RESULT')
            state.write_job(home/'jobs'/'a.json', {
                'job_id':'a', 'project':'demo', 'status':'running', 'role':'qa',
                'target':'abc', 'access':'read', 'network':'local',
                'model':'gpt-5.6-luna', 'reasoning_effort':'xhigh',
                'pid':123, 'watcher_pid':456, 'prompt_file':str(prompt),
                'result_file':str(result), 'output_file':str(home/'jobs'/'a.log'),
            })
            pending = home/'events'/'pending'; pending.mkdir(parents=True)
            (pending/'1.json').write_text(json.dumps({'event_id':'e1','job_id':'a','project':'demo','status':'stalled'}))
            pm_state.set_busy(home, 'https://chatgpt.com/c/old', reason='review', minutes=30)
            before = {p.relative_to(home): p.read_bytes() for p in home.rglob('*') if p.is_file()}

            snap=binding.takeover(home,'demo')

            self.assertEqual(set(snap), {'status','project','supervision','execution','runtime'})
            self.assertEqual(snap['project']['name'], 'demo')
            self.assertEqual(snap['project']['working_state']['data']['goal'], 'ship')
            self.assertEqual(snap['supervision']['role'], 'product_manager')
            self.assertEqual(snap['supervision']['charter']['path'], 'docs/pm-operating-charter.md')
            self.assertTrue(snap['supervision']['charter']['read_first'])
            self.assertEqual(snap['execution']['active_jobs'][0]['job_id'], 'a')
            self.assertEqual(snap['runtime']['binding']['url'], 'https://chatgpt.com/c/old')
            self.assertEqual(snap['runtime']['callbacks']['pending'][0]['job_id'], 'a')
            self.assertTrue(snap['runtime']['pm_state']['effective_busy'])
            self.assertEqual(snap['runtime']['watchers'][0]['watcher_pid'], 456)
            self.assertTrue(snap['runtime']['edge']['configured'])
            self.assertNotIn('PRIVATE PROMPT', json.dumps(snap))
            self.assertNotIn('PRIVATE RESULT', json.dumps(snap))
            after = {p.relative_to(home): p.read_bytes() for p in home.rglob('*') if p.is_file()}
            self.assertEqual(before, after)

if __name__ == '__main__': unittest.main()
