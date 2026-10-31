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

    def test_inspect_reports_uncommitted_working_tree_changes_separately(self):
        with tempfile.TemporaryDirectory() as td:
            h=Path(td); repo=h/'repo'; repo.mkdir()
            subprocess.run(['git','init','-q',str(repo)],check=True)
            subprocess.run(['git','-C',str(repo),'config','user.email','a@b.c'],check=True)
            subprocess.run(['git','-C',str(repo),'config','user.name','T'],check=True)
            (repo/'calculator.py').write_text('def add(a,b): return a+b\n')
            (repo/'test_calculator.py').write_text('assert True\n')
            subprocess.run(['git','-C',str(repo),'add','.'],check=True)
            subprocess.run(['git','-C',str(repo),'commit','-qm','baseline'],check=True)
            job=jobs.create_job(h,'p',repo,'x')
            (repo/'calculator.py').write_text('def add(a,b): return a-b\n')
            (repo/'test_calculator.py').write_text('assert add(1,2)==3\n')

            packet=evidence.inspect_job(h,job['job_id'])

            self.assertEqual(packet['git']['changed_files'], [])
            self.assertEqual(packet['git']['working_tree']['changed_files'], ['calculator.py','test_calculator.py'])
            self.assertEqual(packet['git']['working_tree']['changed_file_count'], 2)
            self.assertFalse(packet['git']['working_tree']['clean'])

    def test_inspect_reports_clean_working_tree_as_zero_changes(self):
        with tempfile.TemporaryDirectory() as td:
            h=Path(td); repo=h/'repo'; repo.mkdir()
            subprocess.run(['git','init','-q',str(repo)],check=True)
            subprocess.run(['git','-C',str(repo),'config','user.email','a@b.c'],check=True)
            subprocess.run(['git','-C',str(repo),'config','user.name','T'],check=True)
            (repo/'calculator.py').write_text('def add(a,b): return a+b\n')
            subprocess.run(['git','-C',str(repo),'add','.'],check=True)
            subprocess.run(['git','-C',str(repo),'commit','-qm','baseline'],check=True)
            job=jobs.create_job(h,'p',repo,'x')

            packet=evidence.inspect_job(h,job['job_id'])

            self.assertTrue(packet['git']['working_tree']['clean'])
            self.assertEqual(packet['git']['working_tree']['changed_files'], [])
            self.assertEqual(packet['git']['working_tree']['changed_file_count'], 0)

    def test_inspect_preserves_committed_change_summary(self):
        with tempfile.TemporaryDirectory() as td:
            h=Path(td); repo=h/'repo'; repo.mkdir()
            subprocess.run(['git','init','-q',str(repo)],check=True)
            subprocess.run(['git','-C',str(repo),'config','user.email','a@b.c'],check=True)
            subprocess.run(['git','-C',str(repo),'config','user.name','T'],check=True)
            (repo/'calculator.py').write_text('def add(a,b): return a+b\n')
            subprocess.run(['git','-C',str(repo),'add','.'],check=True)
            subprocess.run(['git','-C',str(repo),'commit','-qm','baseline'],check=True)
            job=jobs.create_job(h,'p',repo,'x')
            (repo/'calculator.py').write_text('def add(a,b): return a-b\n')
            subprocess.run(['git','-C',str(repo),'add','.'],check=True)
            subprocess.run(['git','-C',str(repo),'commit','-qm','worker-change'],check=True)
            end_head=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
            job['end_head']=end_head
            state.write_job(h/'jobs'/f"{job['job_id']}.json",job)

            packet=evidence.inspect_job(h,job['job_id'])

            self.assertEqual(packet['git']['changed_files'], ['calculator.py'])
            self.assertEqual(packet['git']['changed_file_count'], 1)
            self.assertTrue(packet['git']['working_tree']['clean'])

    def test_large_result_is_previewed_but_full_result_remains_available(self):
        with tempfile.TemporaryDirectory() as td:
            h=Path(td); (h/'jobs').mkdir(); repo=h/'repo'; repo.mkdir(); big='R'*20000
            rp=h/'jobs/j.result.txt'; lp=h/'jobs/j.log'; rp.write_text(big); lp.write_text('log')
            state.write_job(h/'jobs/j.json',{'job_id':'j','project':'p','status':'completed','repo':str(repo),'result_file':str(rp),'output_file':str(lp)})
            compact=evidence.inspect_job(h,'j')
            self.assertTrue(compact['result']['truncated']); self.assertLess(len(compact['result']['text']),len(big))
            full=evidence.inspect_job(h,'j',full_result=True)
            self.assertFalse(full['result']['truncated']); self.assertEqual(full['result']['text'],big)
