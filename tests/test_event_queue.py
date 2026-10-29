import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pmbridge import binding, events, pm_state


class PMStateTests(unittest.TestCase):
    def test_busy_and_idle_are_persistent(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            scope='https://chatgpt.com/c/demo'
            pm_state.set_busy(home, scope=scope, reason='review', minutes=5)
            self.assertTrue(pm_state.is_busy(home, scope))
            pm_state.set_idle(home, scope=scope)
            self.assertFalse(pm_state.is_busy(home, scope))


class EventQueueTests(unittest.TestCase):
    def make_cfg(self, home, project='demo', chat_url=None):
        (home/'projects'/project).mkdir(parents=True)
        (home/'projects'/project/'config.json').write_text(
            json.dumps({'version':1,'name':project,'repo':f'/tmp/{project}',
                        'chat_url':chat_url or f'https://chatgpt.com/c/{project}',
                        'stall_seconds':1200}))

    def write_pending_event(self, home, filename, event_id, job_id, project):
        pending = home/'events'/'pending'
        pending.mkdir(parents=True, exist_ok=True)
        (pending/filename).write_text(json.dumps({
            'event_id': event_id,
            'dedupe_key': f'dedupe-{event_id}',
            'created_at_ns': int(filename.split('-', 1)[0]),
            'job_id': job_id,
            'project': project,
            'role': 'qa',
            'target': project,
            'status': 'completed',
        }))

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
    def test_pending_callback_after_rebind_uses_current_active_binding(self, ui_state, send):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td); self.make_cfg(home, chat_url='https://chatgpt.com/c/old')
            (home/'jobs').mkdir()
            (home/'jobs'/'job-1.json').write_text(json.dumps({
                'job_id': 'job-1', 'project': 'demo', 'role': 'qa', 'status': 'completed',
            }))
            events.enqueue_job_event(home, 'job-1', 'completed')
            binding.rebind(home, 'demo', 'https://chatgpt.com/c/new', source='test')
            ui_state.return_value = {
                'reachable': True, 'composer_nonempty': False, 'generating': False,
                'signature': 'stable',
            }
            send.return_value = {'ok': True, 'returncode': 0, 'error': ''}

            result = events.drain(home)

            self.assertEqual(result['delivered'], 1)
            self.assertEqual(send.call_args.args[0], 'https://chatgpt.com/c/new')

    @patch('pmbridge.events.time.time_ns', side_effect=[1, 2])
    @patch('pmbridge.events.transport_edge.send')
    @patch('pmbridge.events.transport_edge.ui_state')
    def test_cross_project_drain_preserves_dedupe_and_at_most_once(self, ui_state, send, time_ns):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            self.make_cfg(home, 'project-a')
            self.make_cfg(home, 'project-b')
            (home/'jobs').mkdir()
            for job_id, project in [('job-a', 'project-a'), ('job-b', 'project-b')]:
                (home/'jobs'/f'{job_id}.json').write_text(json.dumps({
                    'job_id': job_id, 'project': project, 'status': 'completed'}))

            events.enqueue_job_event(home, 'job-a', 'completed')
            event_b = events.enqueue_job_event(home, 'job-b', 'completed')
            duplicate_b = events.enqueue_job_event(home, 'job-b', 'completed')
            self.assertEqual(duplicate_b['event_id'], event_b['event_id'])

            ui_state.side_effect = lambda url: {
                'reachable': True,
                'composer_nonempty': url.endswith('project-a'),
                'generating': False,
                'signature': url,
            }
            send.return_value = {'ok': True, 'returncode': 0, 'error': ''}

            events.drain(home)
            events.drain(home)

            self.assertEqual(send.call_count, 1)
            self.assertEqual(send.call_args.args[0], 'https://chatgpt.com/c/project-b')
            self.assertEqual([event['job_id'] for event in events.pending_events(home)], ['job-a'])

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
            pm_state.set_busy(home, scope='https://chatgpt.com/c/demo', reason='user_interaction', minutes=5)
            self.assertEqual(events.drain(home)['delivered'], 0)
            self.assertEqual(len(events.pending_events(home)), 2)
            send.assert_not_called()
            pm_state.set_idle(home, scope='https://chatgpt.com/c/demo')
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
                {'reachable':False,'composer_nonempty':False,'generating':False},
                {'reachable':True,'composer_nonempty':False,'generating':True},
                {'reachable':True,'composer_nonempty':True,'generating':False},
            ]:
                ui_state.return_value=state
                self.assertEqual(events.drain(home)['delivered'],0)
                self.assertEqual(len(events.pending_events(home)),1)
            send.assert_not_called()

    @patch('pmbridge.events.transport_edge.current_chat_url')
    @patch('pmbridge.events.transport_edge.send')
    @patch('pmbridge.events.transport_edge.ui_state')
    def test_blocked_project_does_not_block_later_project(self, ui_state, send, current_chat_url):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            self.make_cfg(home, 'project-a', 'https://chatgpt.com/c/project-a')
            self.make_cfg(home, 'project-b', 'https://chatgpt.com/c/project-b')
            self.write_pending_event(home, '00000000000000000001-a.json', 'a1', 'job-a', 'project-a')
            self.write_pending_event(home, '00000000000000000002-b.json', 'b1', 'job-b', 'project-b')

            ui_state.side_effect = lambda url: {
                'reachable': True,
                'composer_nonempty': url.endswith('project-a'),
                'generating': False,
                'signature': url,
            }
            send.return_value = {'ok': True, 'returncode': 0, 'error': ''}

            result = events.drain(home)

            self.assertEqual(result['delivered'], 1)
            self.assertEqual(result['pending'], 1)
            self.assertEqual([event['event_id'] for event in events.pending_events(home)], ['a1'])
            self.assertEqual(send.call_args.args[0], 'https://chatgpt.com/c/project-b')
            self.assertIn('job-b', send.call_args.args[1])
            current_chat_url.assert_not_called()

    @patch('pmbridge.events.transport_edge.send')
    @patch('pmbridge.events.transport_edge.ui_state')
    def test_each_project_keeps_fifo_after_cross_project_skip(self, ui_state, send):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            self.make_cfg(home, 'project-a')
            self.make_cfg(home, 'project-b')
            self.write_pending_event(home, '00000000000000000001-a1.json', 'a1', 'job-a1', 'project-a')
            self.write_pending_event(home, '00000000000000000002-b1.json', 'b1', 'job-b1', 'project-b')
            self.write_pending_event(home, '00000000000000000003-a2.json', 'a2', 'job-a2', 'project-a')
            blocked = {'project-a': True}

            def state_for(url):
                project = url.rsplit('/', 1)[-1]
                return {
                    'reachable': True,
                    'composer_nonempty': blocked.get(project, False),
                    'generating': False,
                    'signature': project,
                }

            ui_state.side_effect = state_for
            send.return_value = {'ok': True, 'returncode': 0, 'error': ''}

            first = events.drain(home)
            self.assertEqual(first['delivered'], 1)
            self.assertEqual([event['event_id'] for event in events.pending_events(home)], ['a1', 'a2'])

            blocked['project-a'] = False
            second = events.drain(home)

            self.assertEqual(second['delivered'], 2)
            self.assertEqual(events.pending_events(home), [])
            self.assertEqual(
                [call.args[1].split()[1] for call in send.call_args_list],
                ['job-b1', 'job-a1', 'job-a2'],
            )

    @patch('pmbridge.events.transport_edge.send')
    @patch('pmbridge.events.transport_edge.ui_state')
    def test_quiet_project_is_not_bypassed_but_other_project_can_deliver(self, ui_state, send):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            self.make_cfg(home, 'project-a')
            self.make_cfg(home, 'project-b')
            self.write_pending_event(home, '00000000000000000001-a.json', 'a1', 'job-a', 'project-a')
            self.write_pending_event(home, '00000000000000000002-b.json', 'b1', 'job-b', 'project-b')

            ui_state.side_effect = lambda url: {
                'reachable': True,
                'composer_nonempty': False,
                'generating': False,
                'signature': url,
                'visibility': 'visible' if url.endswith('project-a') else 'hidden',
                'focused': url.endswith('project-a'),
            }
            send.return_value = {'ok': True, 'returncode': 0, 'error': ''}

            result = events.drain(home, quiet_focused_seconds=60)

            self.assertEqual(result['delivered'], 1)
            self.assertEqual([event['event_id'] for event in events.pending_events(home)], ['a1'])
            self.assertEqual(send.call_args.args[1].split()[1], 'job-b')

    @patch('pmbridge.events.transport_edge.send')
    @patch('pmbridge.events.transport_edge.ui_state')
    def test_busy_conversation_does_not_block_other_conversation(self, ui_state, send):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            self.make_cfg(home, 'project-a', 'https://chatgpt.com/c/chat-a')
            self.make_cfg(home, 'project-b', 'https://chatgpt.com/c/chat-b')
            self.write_pending_event(home, '00000000000000000001-a.json', 'a1', 'job-a', 'project-a')
            self.write_pending_event(home, '00000000000000000002-b.json', 'b1', 'job-b', 'project-b')
            pm_state.set_busy(home, scope='https://chatgpt.com/c/chat-a', reason='review', minutes=5)
            ui_state.return_value = {
                'reachable': True, 'composer_nonempty': False, 'generating': False, 'signature': 'stable'
            }
            send.return_value = {'ok': True, 'returncode': 0, 'error': ''}

            result = events.drain(home)

            self.assertEqual(result['delivered'], 1)
            self.assertEqual([event['event_id'] for event in events.pending_events(home)], ['a1'])
            self.assertEqual(send.call_args.args[0], 'https://chatgpt.com/c/chat-b')

    @patch('pmbridge.events.transport_edge.send')
    @patch('pmbridge.events.transport_edge.ui_state')
    def test_delivery_failure_in_one_conversation_does_not_block_other_conversation(self, ui_state, send):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            self.make_cfg(home, 'project-a', 'https://chatgpt.com/c/chat-a')
            self.make_cfg(home, 'project-b', 'https://chatgpt.com/c/chat-b')
            self.write_pending_event(home, '00000000000000000001-a.json', 'a1', 'job-a', 'project-a')
            self.write_pending_event(home, '00000000000000000002-b.json', 'b1', 'job-b', 'project-b')
            ui_state.return_value = {
                'reachable': True, 'composer_nonempty': False, 'generating': False, 'signature': 'stable'
            }
            def send_result(url, message, home):
                if url.endswith('chat-a'):
                    return {'ok': False, 'returncode': 1, 'error': 'send failed'}
                return {'ok': True, 'returncode': 0, 'error': ''}
            send.side_effect = send_result

            result = events.drain(home)

            self.assertEqual(result['delivered'], 1)
            self.assertEqual([event['event_id'] for event in events.pending_events(home)], ['a1'])
            self.assertEqual([call.args[0] for call in send.call_args_list[:2]], [
                'https://chatgpt.com/c/chat-a', 'https://chatgpt.com/c/chat-b'
            ])



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
