import tempfile
import unittest
from pathlib import Path

from pmbridge import codex_profiles, executor


class ProfileTests(unittest.TestCase):
    def test_install_profiles_are_namespaced_and_local_only(self):
        with tempfile.TemporaryDirectory() as td:
            result = codex_profiles.install(Path(td))
            read_text = Path(result['read-local']).read_text(encoding='utf-8')
            write_text = Path(result['write-local']).read_text(encoding='utf-8')
            self.assertIn('extends = ":read-only"', read_text)
            self.assertIn('mode = "full"', read_text)
            self.assertIn('extends = ":workspace"', write_text)
            for text in (read_text, write_text):
                self.assertIn('network_proxy = true', text)
                self.assertIn('"localhost" = "allow"', text)
                self.assertIn('"127.0.0.1" = "allow"', text)
                self.assertNotIn('"*" = "allow"', text)

    def test_read_local_uses_named_profile_without_sandbox_override(self):
        cmd = executor.build_codex_command(
            Path('/tmp/repo'), Path('/tmp/result'), access='read', network='local', codex=Path('/tmp/codex'))
        self.assertIn('-p', cmd)
        self.assertEqual(cmd[cmd.index('-p')+1], 'pmbridge-read-local')
        self.assertNotIn('-s', cmd)

    def test_write_local_uses_named_profile_without_sandbox_override(self):
        cmd = executor.build_codex_command(
            Path('/tmp/repo'), Path('/tmp/result'), access='write', network='local', codex=Path('/tmp/codex'))
        self.assertIn('-p', cmd)
        self.assertEqual(cmd[cmd.index('-p')+1], 'pmbridge-write-local')
        self.assertNotIn('-s', cmd)

    def test_none_network_keeps_read_sandbox_and_write_auto_approval(self):
        read = executor.build_codex_command(Path('/tmp/repo'), Path('/tmp/result'), access='read', network='none', codex=Path('/tmp/codex'))
        write = executor.build_codex_command(Path('/tmp/repo'), Path('/tmp/result'), access='write', network='none', codex=Path('/tmp/codex'))
        self.assertEqual(read[read.index('-s')+1], 'read-only')
        self.assertNotIn('-s', write)
        self.assertIn('--approve-for-me', write)

if __name__ == '__main__': unittest.main()
