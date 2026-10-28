import tempfile, unittest, json, subprocess
from pathlib import Path
from pmbridge import evidence, jobs, state

class EvidenceTests(unittest.TestCase):
    def test_packet_reads_result_but_not_raw_log_contents(self):
        with tempfile.TemporaryDirectory() as td:
            h=Path(td); (h/'jobs').mkdir(); repo=h/'repo'; repo.mkdir()
            j={'job_id':'j1','project':'p','status':'completed','repo':str(repo),'role':'qa','result_file':str(h/'jobs/j1.result.txt'),'output_file':str(h/'jobs/j1.log'),'start_head':'aaa','end_head':'bbb','exit_code':0}
            state.write_job(h/'jobs/j1.json',j)
            (h/'jobs/j1.result.txt').write_text('FINAL')
            (h/'jobs/j1.log').write_text('SECRET_RAW_LOG\n'*1000)
            p=evidence.inspect_job(h,'j1')
            self.assertEqual(p['result']['text'],'FINAL')
            self.assertEqual(p['raw_evidence']['log']['bytes'],len(('SECRET_RAW_LOG\n'*1000).encode()))
            self.assertNotIn('SECRET_RAW_LOG', json.dumps(p))
            self.assertEqual(p['git']['start_head'],'aaa')
    def test_legacy_job_without_boundaries_still_inspects(self):
        with tempfile.TemporaryDirectory() as td:
            h=Path(td); (h/'jobs').mkdir(); repo=h/'repo'; repo.mkdir()
            state.write_job(h/'jobs/old.json',{'job_id':'old','project':'p','status':'completed','repo':str(repo)})
            p=evidence.inspect_job(h,'old')
            self.assertIsNone(p['git']['start_head'])
            self.assertIsNone(p['result']['text'])
    def test_create_job_records_start_head_when_repo_is_git(self):
        with tempfile.TemporaryDirectory() as td:
            h=Path(td); repo=h/'repo'; repo.mkdir()
            subprocess.run(['git','init','-q',str(repo)],check=True); subprocess.run(['git','-C',str(repo),'config','user.email','a@b.c'],check=True); subprocess.run(['git','-C',str(repo),'config','user.name','T'],check=True)
            (repo/'a').write_text('x'); subprocess.run(['git','-C',str(repo),'add','a'],check=True); subprocess.run(['git','-C',str(repo),'commit','-qm','init'],check=True)
            head=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
            j=jobs.create_job(h,'p',repo,'x')
            self.assertEqual(j['start_head'],head)
