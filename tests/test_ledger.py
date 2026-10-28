import tempfile, unittest
from pathlib import Path
from pmbridge import ledger, config, binding

class LedgerTests(unittest.TestCase):
    def setup(self,h):
        r=h/'r'; r.mkdir(); config.save_project(h,{'version':1,'name':'p','repo':str(r),'chat_url':'https://chatgpt.com/c/x','binding_version':1})
    def test_arbitrary_json_roundtrip_and_patch(self):
        with tempfile.TemporaryDirectory() as td:
            h=Path(td); self.setup(h)
            out=ledger.replace(h,'p',{'goal':'ship','nested':{'x':[1,2]},'freeform':'anything'})
            self.assertEqual(out['data']['nested']['x'],[1,2])
            out=ledger.patch(h,'p',{'goal':'review','extra':True})
            self.assertEqual(out['data']['goal'],'review'); self.assertTrue(out['data']['extra']); self.assertEqual(out['data']['nested']['x'],[1,2])
    def test_handoff_includes_ledger_without_requiring_it(self):
        with tempfile.TemporaryDirectory() as td:
            h=Path(td); self.setup(h)
            self.assertIsNone(binding.handoff(h,'p')['ledger'])
            ledger.replace(h,'p',{'current':'x'})
            self.assertEqual(binding.handoff(h,'p')['ledger']['data']['current'],'x')
