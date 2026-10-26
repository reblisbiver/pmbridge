import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch, MagicMock

from pmbridge import cli, runtime


class RuntimeTests(unittest.TestCase):
    def test_install_runtime_creates_stable_wrapper_and_package_copy(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)/'.pmbridge'
            result = runtime.install(home)
            self.assertTrue((home/'runtime'/'pmbridge'/'cli.py').exists())
            wrapper = (home/'bin'/'pmbridge').read_text(encoding='utf-8')
            self.assertIn('PYTHONPATH', wrapper)
            self.assertIn('-m pmbridge.cli', wrapper)
            self.assertEqual(result['status'], 'READY')


class CliTests(unittest.TestCase):
    @patch('pmbridge.cli.transport_edge.send')
    def test_notify_loads_project_chat_url(self, send):
        send.return_value = {'ok': True, 'returncode': 0, 'error': ''}
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            (home/'projects'/'demo').mkdir(parents=True)
            (home/'projects'/'demo'/'config.json').write_text('{"version":1,"name":"demo","repo":"/tmp/demo","chat_url":"https://chatgpt.com/c/demo","stall_seconds":1200}')
            (home/'jobs').mkdir()
            (home/'jobs'/'j.json').write_text('{"job_id":"j","project":"demo","status":"completed"}')
            out = cli.notify_job(home, 'j', 'completed')
            self.assertTrue(out['ok'])
            send.assert_called_once_with('https://chatgpt.com/c/demo', 'PM_JOB_STATUS j completed', home)

    @patch('pmbridge.cli.spawn_watcher')
    def test_run_project_creates_job_and_spawns_watcher(self, spawn):
        spawn.return_value.pid = 42
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            repo = Path(td)/'repo'; repo.mkdir()
            (home/'projects'/'demo').mkdir(parents=True)
            (home/'projects'/'demo'/'config.json').write_text('{"version":1,"name":"demo","repo":"'+str(repo)+'","chat_url":"https://chatgpt.com/c/demo","stall_seconds":1200}')
            result = cli.run_project(home, 'demo', 'Do work')
            self.assertEqual(result['status'], 'STARTED')
            self.assertEqual(result['watcher_pid'], 42)
            self.assertTrue((home/'jobs'/f"{result['job_id']}.json").exists())

if __name__ == '__main__':
    unittest.main()
