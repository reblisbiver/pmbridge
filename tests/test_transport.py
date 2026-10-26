import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from pmbridge import transport_edge


class EdgeTransportTests(unittest.TestCase):
    def test_template_is_generic_background_and_busy_composer_safe(self):
        s = transport_edge.SCRIPT.read_text(encoding='utf-8')
        self.assertIn('BUSY_COMPOSER', s)
        self.assertIn('delay 2.0', s)
        self.assertIn('repeat with sendAttempt from 1 to 1', s)
        self.assertIn('if URL of t is targetURL', s)
        self.assertIn('PM_CHAT_URL is required', s)
        self.assertNotIn('https://chatgpt.com/c/', s)
        self.assertNotIn('/Users/', s)
        self.assertNotIn('activate', s.lower())
        self.assertNotIn('system events', s.lower())
        self.assertNotIn('keystroke', s.lower())

    @patch('pmbridge.transport_edge.subprocess.run')
    def test_send_uses_environment_not_embedded_personal_config(self, run):
        run.return_value.returncode = 0
        run.return_value.stdout = ''
        run.return_value.stderr = ''
        with tempfile.TemporaryDirectory() as td:
            result = transport_edge.send('https://chatgpt.com/c/demo', 'PM_JOB_STATUS j completed', Path(td))
        self.assertTrue(result['ok'])
        self.assertEqual(run.call_args.args[0][0], str(transport_edge.SCRIPT))
        self.assertEqual(run.call_args.args[0][1], 'PM_JOB_STATUS j completed')
        env = run.call_args.kwargs['env']
        self.assertEqual(env['PM_CHAT_URL'], 'https://chatgpt.com/c/demo')
        self.assertTrue(env['PM_BRIDGE_LOG_DIR'].endswith('/logs'))

if __name__ == '__main__':
    unittest.main()

class DiscoverChatTests(unittest.TestCase):
    @patch('pmbridge.transport_edge.subprocess.run')
    def test_current_chat_url_returns_active_chatgpt_conversation(self, run):
        run.return_value.returncode = 0
        run.return_value.stdout = 'https://chatgpt.com/c/abc123\n'
        run.return_value.stderr = ''
        self.assertEqual(transport_edge.current_chat_url(), 'https://chatgpt.com/c/abc123')

    @patch('pmbridge.transport_edge.subprocess.run')
    def test_current_chat_url_rejects_non_conversation_tab(self, run):
        run.return_value.returncode = 0
        run.return_value.stdout = 'https://chatgpt.com/\n'
        run.return_value.stderr = ''
        self.assertIsNone(transport_edge.current_chat_url())

class TokenBindingTests(unittest.TestCase):
    @patch('pmbridge.transport_edge.subprocess.run')
    def test_find_chat_by_token_returns_unique_match(self, run):
        run.return_value.returncode = 0
        run.return_value.stdout = 'https://chatgpt.com/c/current\n'
        run.return_value.stderr = ''
        result = transport_edge.find_chat_by_token('PMBRIDGE_BIND_X')
        self.assertEqual(result, {'status': 'FOUND', 'url': 'https://chatgpt.com/c/current'})

    @patch('pmbridge.transport_edge.subprocess.run')
    def test_find_chat_by_token_rejects_ambiguous_match(self, run):
        run.return_value.returncode = 0
        run.return_value.stdout = 'https://chatgpt.com/c/a\nhttps://chatgpt.com/c/b\n'
        run.return_value.stderr = ''
        result = transport_edge.find_chat_by_token('PMBRIDGE_BIND_X')
        self.assertEqual(result['status'], 'AMBIGUOUS_CHAT_BINDING')

    @patch('pmbridge.transport_edge.subprocess.run')
    def test_find_chat_by_token_reports_missing(self, run):
        run.return_value.returncode = 0
        run.return_value.stdout = ''
        run.return_value.stderr = ''
        result = transport_edge.find_chat_by_token('PMBRIDGE_BIND_X')
        self.assertEqual(result['status'], 'CHAT_BINDING_NOT_FOUND')

class TokenBindingRetryTests(unittest.TestCase):
    @patch('pmbridge.transport_edge.time.sleep')
    @patch('pmbridge.transport_edge.subprocess.run')
    def test_find_chat_by_token_can_wait_for_dom_render(self, run, sleep):
        first = MagicMock(returncode=0, stdout='', stderr='')
        second = MagicMock(returncode=0, stdout='https://chatgpt.com/c/current\n', stderr='')
        run.side_effect = [first, second]
        result = transport_edge.find_chat_by_token('PMBRIDGE_BIND_X', attempts=2, delay=0.1)
        self.assertEqual(result['status'], 'FOUND')
        sleep.assert_called_once_with(0.1)

class TextBindingTests(unittest.TestCase):
    @patch('pmbridge.transport_edge.subprocess.run')
    def test_find_chat_by_texts_returns_unique_match(self, run):
        run.return_value.returncode = 0
        run.return_value.stdout = 'https://chatgpt.com/c/current\n'
        run.return_value.stderr = ''
        result = transport_edge.find_chat_by_texts(['distinctive setup request', 'start now'])
        self.assertEqual(result, {'status': 'FOUND', 'url': 'https://chatgpt.com/c/current'})

    @patch('pmbridge.transport_edge.subprocess.run')
    def test_find_chat_by_texts_rejects_ambiguous_match(self, run):
        run.return_value.returncode = 0
        run.return_value.stdout = 'https://chatgpt.com/c/a\nhttps://chatgpt.com/c/b\n'
        run.return_value.stderr = ''
        result = transport_edge.find_chat_by_texts(['same text'])
        self.assertEqual(result['status'], 'AMBIGUOUS_CHAT_BINDING')

    def test_find_chat_by_texts_requires_nonempty_markers(self):
        self.assertEqual(transport_edge.find_chat_by_texts([])['status'], 'NEEDS_CHAT_BINDING')
