import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from pmbridge import cli, config


class ProjectDiscoveryTests(unittest.TestCase):
    def test_list_projects_returns_registered_projects_sorted_without_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            repo_a = home / 'repos' / 'alpha'
            repo_a.mkdir(parents=True)
            config.save_project(home, {
                'name': 'zeta', 'repo': str(home / 'missing-zeta'),
                'chat_url': 'https://chatgpt.com/c/zeta', 'binding_version': 2,
                'binding_guarded': True,
            })
            config.save_project(home, {
                'name': 'alpha', 'repo': str(repo_a),
                'chat_url': 'https://chatgpt.com/c/alpha', 'binding_version': 1,
                'binding_guarded': False,
            })
            before = {p.relative_to(home): p.read_bytes() for p in home.rglob('*') if p.is_file()}

            projects = config.list_projects(home)

            self.assertEqual([p['name'] for p in projects], ['alpha', 'zeta'])
            self.assertEqual(projects[0]['repo'], str(repo_a))
            self.assertTrue(projects[0]['repo_exists'])
            self.assertFalse(projects[1]['repo_exists'])
            self.assertEqual(projects[1]['binding_version'], 2)
            self.assertTrue(projects[1]['binding_guarded'])
            after = {p.relative_to(home): p.read_bytes() for p in home.rglob('*') if p.is_file()}
            self.assertEqual(before, after)

    def test_list_projects_empty_registry_is_empty(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(config.list_projects(Path(td)), [])

    def test_list_projects_ignores_malformed_entries(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            broken = home / 'projects' / 'broken'
            broken.mkdir(parents=True)
            (broken / 'config.json').write_text('{not-json', encoding='utf-8')
            config.save_project(home, {
                'name': 'good', 'repo': str(home / 'good'),
                'chat_url': 'https://chatgpt.com/c/good',
            })
            self.assertEqual([p['name'] for p in config.list_projects(home)], ['good'])

    def test_projects_list_cli_outputs_registry(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            config.save_project(home, {
                'name': 'demo', 'repo': str(home / 'demo'),
                'chat_url': 'https://chatgpt.com/c/demo',
            })
            out = io.StringIO()
            with redirect_stdout(out):
                code = cli.main(['projects', 'list', '--home', str(home), '--json'])
            payload = json.loads(out.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(payload['status'], 'READY')
            self.assertEqual(payload['count'], 1)
            self.assertEqual(payload['projects'][0]['name'], 'demo')

    def test_replacement_pm_docs_require_registry_before_takeover_and_disk_search_only_as_fallback(self):
        setup = Path('CHATGPT_SETUP.md').read_text(encoding='utf-8')
        section = setup.split('## Replacing a full ChatGPT PM conversation', 1)[1]
        list_pos = section.find('pmbridge projects list --json')
        takeover_pos = section.find('pmbridge takeover <project-name> --json')
        self.assertGreaterEqual(list_pos, 0)
        self.assertGreater(takeover_pos, list_pos)
        self.assertIn('filesystem search is a fallback only', section.lower())


if __name__ == '__main__':
    unittest.main()
