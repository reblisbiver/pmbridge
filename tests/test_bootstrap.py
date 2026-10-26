import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from pmbridge import config, gitops


class BootstrapTests(unittest.TestCase):
    def test_non_git_repo_requires_confirmation_without_side_effect(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = gitops.ensure_repo(root, init_repo=False)
            self.assertEqual(result['status'], 'NEEDS_REPO_CONFIRMATION')
            self.assertFalse((root / '.git').exists())

    def test_explicit_repo_init_creates_repo(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = gitops.ensure_repo(root, init_repo=True)
            self.assertEqual(result['status'], 'READY')
            self.assertTrue((root / '.git').exists())
            self.assertEqual(subprocess.check_output(['git','-C',td,'branch','--show-current'], text=True).strip(), 'main')

    def test_config_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            cfg = {
                'version': 1,
                'name': 'demo',
                'repo': '/tmp/demo',
                'chat_url': 'https://chatgpt.com/c/example',
                'stall_seconds': 1200,
            }
            path = config.save_project(home, cfg)
            self.assertTrue(path.exists())
            self.assertEqual(config.load_project(home, 'demo'), cfg)

    def test_project_name_defaults_to_repo_directory(self):
        self.assertEqual(config.default_project_name(Path('/tmp/my-project')), 'my-project')

if __name__ == '__main__':
    unittest.main()
