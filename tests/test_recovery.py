import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pmbridge import launchd, recovery, state


class RecoveryTests(unittest.TestCase):
    def job(self, td, status='running', pid=100, watcher_pid=200):
        p = Path(td)/'jobs'/'j.json'
        state.write_job(p, {'job_id':'j','status':status,'pid':pid,'watcher_pid':watcher_pid,'notified_terminal':False})
        return p

    @patch('pmbridge.recovery.state.process_alive')
    def test_live_job_with_live_watcher_does_nothing(self, alive):
        alive.side_effect = lambda pid: pid in {100,200}
        with tempfile.TemporaryDirectory() as td:
            p = self.job(td)
            self.assertEqual(recovery.recovery_action(state.load_job(p)), 'none')

    @patch('pmbridge.recovery.state.process_alive')
    def test_live_codex_missing_watcher_reattaches(self, alive):
        alive.side_effect = lambda pid: pid == 100
        with tempfile.TemporaryDirectory() as td:
            p = self.job(td)
            self.assertEqual(recovery.recovery_action(state.load_job(p)), 'reattach')

    @patch('pmbridge.recovery.state.process_alive', return_value=False)
    def test_dead_active_job_interrupts(self, alive):
        with tempfile.TemporaryDirectory() as td:
            p = self.job(td)
            self.assertEqual(recovery.recovery_action(state.load_job(p)), 'interrupt')

    @patch('pmbridge.recovery.state.process_alive', return_value=False)
    def test_completed_job_never_interrupts(self, alive):
        with tempfile.TemporaryDirectory() as td:
            p = self.job(td, status='completed')
            self.assertEqual(recovery.recovery_action(state.load_job(p)), 'none')


class LaunchdTests(unittest.TestCase):
    def test_plist_contains_global_recovery_command(self):
        text = launchd.render_plist(Path('/Users/example/.pmbridge'))
        self.assertIn('com.pmbridge.recovery', text)
        self.assertIn('/Users/example/.pmbridge/bin/pmbridge', text)
        self.assertIn('<string>recovery</string>', text)
        self.assertIn('<integer>60</integer>', text)

if __name__ == '__main__':
    unittest.main()
