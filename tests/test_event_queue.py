import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pmbridge import events, pm_state


class PMStateTests(unittest.TestCase):
    def test_busy_and_idle_are_persistent(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            pm_state.set_busy(home, reason='review', minutes=5)
            self.assertTrue(pm_state.is_busy(home))
            pm_state.set_idle(home)
            self.assertFalse(pm_state.is_busy(home))


class EventQueueTests(unittest.TestCase):
    def make_cfg(self, home):
        (home/'projects'/'demo').mkdir(parents=True)
        (home/'projects'/'demo'/'config.json').write_text(
            json.dumps({'version':1,'name':'demo','repo':'/tmp/demo','chat_url':'https://chatgpt.com/c/demo','stall_seconds':1200}))

    def test_enqueue_is_fifo_and_preserves_job_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td); self.make_cfg(home); (home/'jobs').mkdir()
            for job_id, role, target in [('j1','qa','a'),('j2','blackbox','a')]:
                (home/'jobs'/f'{job_id}.json').write_text(json.dumps({
                    'job_id':job_id,'project':'demo','role':role,'target':target,'status':'completed'}))
            e1 = events.enqueue_job_event(home, 'j1', 'completed')
            e2 = events.enqueue_job_event(home, 'j2', 'completed')
            pending = events.pending_events(home)
            self.assertEqual([x['event_id'] for x in pending], [e1['event_id'], e2['event_id']])
            self.assertEqual(pending[0]['role'], 'qa')
            self.assertEqual(pending[1]['target'], 'a')

    @patch('pmbridge.events.transport_edge.send')
    @patch('pmbridge.events.transport_edge.ui_state')
    def test_busy_pm_queues_without_delivery_then_idle_drains_fifo(self, ui_state, send):
        ui_state.return_value = {'reachable':True,'composer_nonempty':False,'generating':False}
        send.return_value = {'ok':True,'returncode':0,'error':''}
        with tempfile.TemporaryDirectory() as td:
            home=Path(td); self.make_cfg(home); (home/'jobs').mkdir()
            for job_id in ['j1','j2']:
                (home/'jobs'/f'{job_id}.json').write_text(json.dumps({'job_id':job_id,'project':'demo','role':'qa','target':'a','status':'completed'}))
                events.enqueue_job_event(home, job_id, 'completed')
            pm_state.set_busy(home, reason='user_interaction', minutes=5)
            self.assertEqual(events.drain(home)['delivered'], 0)
            self.assertEqual(len(events.pending_events(home)), 2)
            send.assert_not_called()
            pm_state.set_idle(home)
            out = events.drain(home)
            self.assertEqual(out['delivered'], 2)
            self.assertEqual(len(events.pending_events(home)), 0)
            calls=[c.args[1] for c in send.call_args_list]
            self.assertTrue(calls[0].startswith('PM_JOB_STATUS j1 completed'))
            self.assertTrue(calls[1].startswith('PM_JOB_STATUS j2 completed'))

    @patch('pmbridge.events.transport_edge.send')
    @patch('pmbridge.events.transport_edge.ui_state')
    def test_generating_or_composer_draft_blocks_delivery(self, ui_state, send):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td); self.make_cfg(home); (home/'jobs').mkdir()
            (home/'jobs'/'j.json').write_text(json.dumps({'job_id':'j','project':'demo','role':'qa','status':'completed'}))
            events.enqueue_job_event(home,'j','completed')
            for state in [
                {'reachable':True,'composer_nonempty':False,'generating':True},
                {'reachable':True,'composer_nonempty':True,'generating':False},
            ]:
                ui_state.return_value=state
                self.assertEqual(events.drain(home)['delivered'],0)
                self.assertEqual(len(events.pending_events(home)),1)
            send.assert_not_called()


if __name__ == '__main__':
    unittest.main()

class QuietWindowTests(unittest.TestCase):
    @patch('pmbridge.events.transport_edge.send')
    @patch('pmbridge.events.transport_edge.ui_state')
    def test_visible_chat_requires_quiet_window_before_delivery(self, ui_state, send):
        ui_state.return_value = {'reachable':True,'composer_nonempty':False,'generating':False,'signature':'stable','visibility':'visible','focused':True}
        send.return_value = {'ok':True,'returncode':0,'error':''}
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            (home/'projects'/'demo').mkdir(parents=True)
            (home/'projects'/'demo'/'config.json').write_text(json.dumps({'version':1,'name':'demo','repo':'/tmp/demo','chat_url':'https://chatgpt.com/c/demo','stall_seconds':1200}))
            (home/'jobs').mkdir()
            (home/'jobs'/'j.json').write_text(json.dumps({'job_id':'j','project':'demo','role':'qa','status':'completed'}))
            events.enqueue_job_event(home,'j','completed')
            out=events.drain(home, wait_seconds=0, quiet_focused_seconds=12, quiet_background_seconds=4)
            self.assertEqual(out['status'],'UI_QUIET_WAIT')
            send.assert_not_called()
