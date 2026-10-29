import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pmbridge import executor, jobs, cli, state


class ExecutionPolicyTests(unittest.TestCase):
    def test_default_model_and_reasoning_are_explicit(self):
        cmd = executor.build_codex_command(Path('/tmp/repo'), Path('/tmp/result'), access='write')
        self.assertIn('-m', cmd)
        self.assertEqual(cmd[cmd.index('-m') + 1], 'gpt-5.6-luna')
        self.assertIn('-c', cmd)
        self.assertIn('model_reasoning_effort="high"', cmd)
        self.assertIn('--approve-for-me', cmd)
        self.assertNotIn('-s', cmd)

    def test_read_access_is_real_codex_read_only_and_overrides_are_explicit(self):
        cmd = executor.build_codex_command(
            Path('/tmp/repo'), Path('/tmp/result'), access='read',
            model='gpt-test', reasoning_effort='high', codex=Path('/tmp/codex'))
        self.assertEqual(cmd[0], '/tmp/codex')
        self.assertEqual(cmd[cmd.index('-m') + 1], 'gpt-test')
        self.assertIn('model_reasoning_effort="high"', cmd)
        self.assertIn('-s', cmd)
        self.assertEqual(cmd[cmd.index('-s') + 1], 'read-only')
        self.assertNotIn('--approve-for-me', cmd)

    def test_write_without_network_uses_auto_approval_without_explicit_sandbox(self):
        cmd = executor.build_codex_command(
            Path('/tmp/repo'), Path('/tmp/result'), access='write', network='none', codex=Path('/tmp/codex'))
        self.assertIn('--approve-for-me', cmd)
        self.assertNotIn('-s', cmd)

    def test_omitted_access_does_not_impose_sandbox_policy(self):
        cmd = executor.build_codex_command(
            Path('/tmp/repo'), Path('/tmp/result'), access=None, network='none', codex=Path('/tmp/codex'))
        self.assertNotIn('-s', cmd)
        self.assertNotIn('-p', cmd)
        self.assertNotIn('--approve-for-me', cmd)

    def test_local_network_requires_explicit_access(self):
        with self.assertRaisesRegex(ValueError, 'network=local requires explicit access'):
            executor.build_codex_command(
                Path('/tmp/repo'), Path('/tmp/result'), access=None, network='local', codex=Path('/tmp/codex'))


    def test_omitted_network_does_not_impose_network_policy(self):
        cmd = executor.build_codex_command(
            Path('/tmp/repo'), Path('/tmp/result'), access=None, network=None, codex=Path('/tmp/codex'))
        self.assertNotIn('-p', cmd)

    def test_internet_network_uses_named_profile(self):
        cmd = executor.build_codex_command(
            Path('/tmp/repo'), Path('/tmp/result'), access='read', network='internet', codex=Path('/tmp/codex'))
        self.assertIn('-p', cmd)
        self.assertEqual(cmd[cmd.index('-p') + 1], 'pmbridge-read-internet')

    def test_job_records_role_access_target_model_and_reasoning(self):
        with tempfile.TemporaryDirectory() as td:
            job = jobs.create_job(
                Path(td), 'demo', Path('/tmp/repo'), 'Audit it', 600,
                role='qa', access='read', network='local', target='abc123',
                model='gpt-5.6-luna', reasoning_effort='xhigh')
            self.assertEqual(job['role'], 'qa')
            self.assertEqual(job['access'], 'read')
            self.assertEqual(job['network'], 'local')
            self.assertEqual(job['target'], 'abc123')
            self.assertEqual(job['model'], 'gpt-5.6-luna')
            self.assertEqual(job['reasoning_effort'], 'xhigh')

    @patch('pmbridge.cli.spawn_watcher')
    def test_multiple_jobs_can_start_for_same_project(self, spawn):
        spawn.side_effect = [type('P', (), {'pid': 11})(), type('P', (), {'pid': 12})()]
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            repo = home/'repo'; repo.mkdir()
            (home/'projects'/'demo').mkdir(parents=True)
            (home/'projects'/'demo'/'config.json').write_text(
                '{"version":1,"name":"demo","repo":"'+str(repo)+'","chat_url":"https://chatgpt.com/c/demo","stall_seconds":1200}')
            a = cli.run_project(home, 'demo', 'Implement', role='implementer', access='write')
            b = cli.run_project(home, 'demo', 'Audit', role='qa', access='read', network='local', target='commit-a')
            self.assertNotEqual(a['job_id'], b['job_id'])
            ja = state.load_job(home/'jobs'/f"{a['job_id']}.json")
            jb = state.load_job(home/'jobs'/f"{b['job_id']}.json")
            self.assertEqual((ja['role'], ja['access']), ('implementer', 'write'))
            self.assertEqual((jb['role'], jb['access'], jb['network'], jb['target']), ('qa', 'read', 'local', 'commit-a'))


if __name__ == '__main__':
    unittest.main()
