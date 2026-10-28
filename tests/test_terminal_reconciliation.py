import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pmbridge import recovery, state, watcher


class TerminalReconciliationTests(unittest.TestCase):
    def make_job(self, root: Path, *, status='running', result=False, notified=False):
        jobs = root / 'jobs'; jobs.mkdir(parents=True, exist_ok=True)
        repo = root / 'repo'; repo.mkdir(exist_ok=True)
        result_file = jobs / 'j.result.txt'
        if result:
            result_file.write_text('done', encoding='utf-8')
        path = jobs / 'j.json'
        state.write_job(path, {
            'job_id': 'j', 'project': 'demo', 'status': status,
            'pid': 100, 'watcher_pid': 200, 'notified_terminal': notified,
            'repo': str(repo), 'result_file': str(result_file),
            'output_file': str(jobs / 'j.log'),
        })
        return path

    @patch('pmbridge.recovery.state.process_alive', return_value=False)
    def test_dead_active_job_with_its_result_reconciles_completed(self, _alive):
        with tempfile.TemporaryDirectory() as td:
            path = self.make_job(Path(td), result=True)
            self.assertEqual(recovery.recovery_action(state.load_job(path)), 'complete')

    @patch('pmbridge.recovery.state.process_alive', return_value=False)
    def test_dead_active_job_without_result_remains_interrupted(self, _alive):
        with tempfile.TemporaryDirectory() as td:
            path = self.make_job(Path(td), result=False)
            self.assertEqual(recovery.recovery_action(state.load_job(path)), 'interrupt')

    @patch('pmbridge.recovery.state.process_alive', return_value=False)
    def test_terminal_job_with_missing_notification_is_replayed(self, _alive):
        with tempfile.TemporaryDirectory() as td:
            path = self.make_job(Path(td), status='completed', result=True, notified=False)
            self.assertEqual(recovery.recovery_action(state.load_job(path)), 'notify')

    @patch('pmbridge.watcher.notify')
    @patch('pmbridge.watcher.state.process_alive', return_value=False)
    def test_attach_dead_job_with_result_completes_and_notifies_once(self, _alive, notify):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = self.make_job(root, result=True)
            code = watcher.attach_job(root, 'j', poll_seconds=0)
            job = state.load_job(path)
            self.assertEqual(code, 0)
            self.assertEqual(job['status'], 'completed')
            self.assertTrue(job['notified_terminal'])
            notify.assert_called_once_with(root, 'j', 'completed')

            watcher.attach_job(root, 'j', poll_seconds=0)
            notify.assert_called_once()
