import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pmbridge import doctor


class DoctorTests(unittest.TestCase):
    @patch('pmbridge.doctor.transport_edge.probe', return_value={'ok': True, 'detail': 'reachable'})
    @patch('pmbridge.doctor.executor.find_codex')
    def test_doctor_ready_when_required_components_exist(self, codex, probe):
        codex.return_value = Path('/tmp/codex')
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = root/'repo'; repo.mkdir(); (repo/'.git').mkdir()
            home = root/'.pmbridge'
            (home/'projects'/'demo').mkdir(parents=True)
            (home/'projects'/'demo'/'config.json').write_text('{"version":1,"name":"demo","repo":"'+str(repo)+'","chat_url":"https://chatgpt.com/c/demo","stall_seconds":1200}')
            (home/'bin').mkdir(parents=True); (home/'bin'/'pmbridge').write_text('#!/bin/zsh\n')
            result = doctor.check(home, 'demo', edge_exists=True, launchd_loaded=True)
            self.assertEqual(result['status'], 'READY')
            self.assertTrue(all(c['ok'] for c in result['checks']))

    @patch('pmbridge.doctor.transport_edge.probe', return_value={'ok': False, 'detail': 'tab missing'})
    @patch('pmbridge.doctor.executor.find_codex', side_effect=FileNotFoundError('Codex CLI not found'))
    def test_doctor_reports_actionable_failures(self, codex, probe):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); home=root/'.pmbridge'; repo=root/'repo'; repo.mkdir()
            (home/'projects'/'demo').mkdir(parents=True)
            (home/'projects'/'demo'/'config.json').write_text('{"version":1,"name":"demo","repo":"'+str(repo)+'","chat_url":"https://chatgpt.com/c/demo","stall_seconds":1200}')
            result=doctor.check(home,'demo',edge_exists=False,launchd_loaded=False)
            self.assertEqual(result['status'], 'NOT_READY')
            names={c['name']:c for c in result['checks']}
            self.assertFalse(names['codex']['ok'])
            self.assertFalse(names['edge']['ok'])
            self.assertFalse(names['chat_tab']['ok'])
            self.assertFalse(names['supervisor']['ok'])

if __name__ == '__main__':
    unittest.main()
