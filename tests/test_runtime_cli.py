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
    @patch('pmbridge.cli.spawn_event_drain')
    @patch('pmbridge.cli.events.enqueue_job_event')
    def test_notify_queues_event_and_starts_single_drain(self, enqueue, drain):
        enqueue.return_value = {'event_id':'e1','job_id':'j','status':'completed'}
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            out = cli.notify_job(home, 'j', 'completed')
            self.assertTrue(out['queued'])
            enqueue.assert_called_once_with(home, 'j', 'completed')
            drain.assert_called_once_with(home)


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

class PMCliParsingTests(unittest.TestCase):
    def test_pm_status_accepts_json_after_subcommand(self):
        args = cli.build_parser().parse_args(['pm','status','--json'])
        self.assertEqual(args.command, 'pm')
        self.assertEqual(args.pm_command, 'status')
        self.assertTrue(args.json)

    def test_pm_busy_accepts_home_and_json_after_subcommand(self):
        args = cli.build_parser().parse_args(['pm','busy','--reason','review','--minutes','5','--home','/tmp/x','--json'])
        self.assertEqual(args.home, '/tmp/x')
        self.assertTrue(args.json)
