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
            result = runtime.install(home, codex_home=Path(td)/'.codex')
            self.assertTrue((home/'runtime'/'pmbridge'/'cli.py').exists())
            wrapper = (home/'bin'/'pmbridge').read_text(encoding='utf-8')
            self.assertIn('PYTHONPATH', wrapper)
            self.assertIn('-m pmbridge.cli', wrapper)
            self.assertEqual(result['status'], 'READY')
            self.assertTrue((Path(td)/'.codex'/'pmbridge-read-local.config.toml').exists())
            self.assertTrue((Path(td)/'.codex'/'pmbridge-write-local.config.toml').exists())


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


class OptionalAccessCliTests(unittest.TestCase):
    def test_run_parser_allows_access_to_be_omitted(self):
        args = cli.build_parser().parse_args(['run', 'demo', '--instruction', 'Do work'])
        self.assertIsNone(args.access)


class PMCommandScopeTests(unittest.TestCase):
    def test_pm_busy_accepts_explicit_project_and_keeps_legacy_parse_compatible(self):
        parser = cli.build_parser()
        args = parser.parse_args(['pm', 'busy', 'demo', '--reason', 'review'])
        self.assertEqual(args.project, 'demo')
        legacy = parser.parse_args(['pm', 'busy', '--reason', 'review'])
        self.assertIsNone(legacy.project)

    def test_pm_scope_infers_only_single_project(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            (home/'projects'/'solo').mkdir(parents=True)
            (home/'projects'/'solo'/'config.json').write_text(
                '{"version":1,"name":"solo","repo":"/tmp/solo","chat_url":"https://chatgpt.com/c/solo"}')
            self.assertEqual(cli._resolve_pm_project_scope(home), ('solo', 'https://chatgpt.com/c/solo'))
            (home/'projects'/'other').mkdir(parents=True)
            (home/'projects'/'other'/'config.json').write_text(
                '{"version":1,"name":"other","repo":"/tmp/other","chat_url":"https://chatgpt.com/c/other"}')
            with self.assertRaisesRegex(ValueError, 'requires <project>'):
                cli._resolve_pm_project_scope(home)

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

class RebindCliTests(unittest.TestCase):
    def test_rebind_parser_accepts_safe_chat_markers(self):
        args = cli.build_parser().parse_args(['rebind','demo','--chat-bind-text','hello','--chat-bind-text','world','--json'])
        self.assertEqual(args.command, 'rebind')
        self.assertEqual(args.project, 'demo')
        self.assertEqual(args.chat_bind_text, ['hello','world'])
        self.assertTrue(args.json)

    def test_handoff_parser(self):
        args = cli.build_parser().parse_args(['handoff','demo','--json'])
        self.assertEqual(args.command, 'handoff')
        self.assertEqual(args.project, 'demo')
        self.assertTrue(args.json)

    @patch('pmbridge.cli.doctor.check')
    @patch('pmbridge.cli.binding.rebind')
    @patch('pmbridge.cli.transport_edge.find_chat_by_texts')
    def test_rebind_uses_unique_discovery_then_doctor(self, discover, rebind, doctor_check):
        discover.return_value = {'status':'FOUND','url':'https://chatgpt.com/c/new'}
        rebind.return_value = {'status':'READY','project':'demo','chat_url':'https://chatgpt.com/c/new','binding_version':2}
        doctor_check.return_value = {'status':'READY','project':'demo','checks':[]}
        args = cli.build_parser().parse_args(['rebind','demo','--chat-bind-text','hello','--json'])
        result = cli.rebind_project(Path('/tmp/home'), args)
        discover.assert_called_once()
        rebind.assert_called_once_with(Path('/tmp/home'), 'demo', 'https://chatgpt.com/c/new', source='chat-bind-text')
        doctor_check.assert_called_once_with(Path('/tmp/home'), 'demo')
        self.assertEqual(result['status'],'READY')
        self.assertEqual(result['doctor']['status'],'READY')

    @patch('pmbridge.cli.transport_edge.find_chat_by_texts')
    def test_failed_discovery_does_not_rebind(self, discover):
        discover.return_value = {'status':'AMBIGUOUS_CHAT_BINDING','matches':['a','b']}
        args = cli.build_parser().parse_args(['rebind','demo','--chat-bind-text','hello','--json'])
        result = cli.rebind_project(Path('/tmp/home'), args)
        self.assertEqual(result['status'],'AMBIGUOUS_CHAT_BINDING')
