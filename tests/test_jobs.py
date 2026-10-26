import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pmbridge import jobs, state


class StateTests(unittest.TestCase):
    def make_job(self, td):
        root = Path(td)
        p = root / 'job.json'
        state.write_job(p, {'job_id':'j1','status':'running','pid':123,'watcher_pid':456,'notified_terminal':False,'notified_stalled':False})
        return p

    def test_terminal_state_cannot_regress(self):
        with tempfile.TemporaryDirectory() as td:
            p = self.make_job(td)
            state.safe_transition(p, status='completed', exit_code=0)
            state.safe_transition(p, status='interrupted')
            job = state.load_job(p)
            self.assertEqual(job['status'], 'completed')
            self.assertEqual(job['exit_code'], 0)

    def test_claim_flag_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            p = self.make_job(td)
            self.assertTrue(state.claim_flag(p, 'notified_terminal'))
            self.assertFalse(state.claim_flag(p, 'notified_terminal'))

    def test_safe_transition_preserves_unspecified_watcher_pid(self):
        with tempfile.TemporaryDirectory() as td:
            p = self.make_job(td)
            state.safe_transition(p, status='running', pid=999)
            self.assertEqual(state.load_job(p)['watcher_pid'], 456)


class JobCreationTests(unittest.TestCase):
    def test_create_job_writes_tagged_prompt_and_state(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch('pmbridge.jobs.uuid.uuid4', return_value='job-123'):
                job = jobs.create_job(root, 'demo', Path('/tmp/repo'), 'Do work', 600)
            self.assertEqual(job['job_id'], 'job-123')
            self.assertEqual(job['status'], 'starting')
            prompt = Path(job['prompt_file']).read_text(encoding='utf-8')
            self.assertTrue(prompt.startswith('[PM_BRIDGE_TASK:job-123]\n'))
            self.assertIn('Do work', prompt)
            self.assertEqual(job['stall_seconds'], 600)

if __name__ == '__main__':
    unittest.main()
