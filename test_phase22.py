import os
import time
import json
import unittest
import shutil

from app import app, jobs
from database.sqlite import init_db, DB_PATH
from core.baseline import BASELINE_DIR

class TestPhase22(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['PROPAGATE_EXCEPTIONS'] = True
        self.client = app.test_client()
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        if os.path.exists(BASELINE_DIR):
            shutil.rmtree(BASELINE_DIR)
        init_db()

    def tearDown(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        if os.path.exists(BASELINE_DIR):
            shutil.rmtree(BASELINE_DIR)

    def test_landing_page_loads(self):
        """landing page loads"""
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn("BEHAVE", html)
        self.assertIn("TRY DEMO", html)
        self.assertIn("AI BEHAVIOR TEST LAB", html)
        self.assertIn("Does your AI actually get better", html)

    def test_demo_launches_and_executes(self):
        """demo launches, executes real evaluation, and progress state works"""
        # Start demo
        res = self.client.post('/api/demo/start')
        if res.status_code != 200:
            print("ERROR in demo start:", res.data)
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        job_id = data.get("job_id")
        self.assertIsNotNone(job_id)

        # Check progress
        res_prog = self.client.get(f'/api/jobs/{job_id}')
        prog_data = json.loads(res_prog.data)
        self.assertEqual(prog_data['status'], 'RUNNING')
        self.assertIn('progress', prog_data)

        # Wait for completion (since it's a fast local mock execution, ~1 sec)
        max_wait = 20
        completed = False
        for _ in range(max_wait):
            time.sleep(0.5)
            r = self.client.get(f'/api/jobs/{job_id}')
            d = json.loads(r.data)
            if d['status'] == 'COMPLETED':
                completed = True
                break
            elif d['status'] == 'FAILED':
                break
        
        self.assertTrue(completed, "Demo did not complete successfully.")
        
        # Check export works
        exp_id = d['experiment_id']
        res_exp = self.client.get(f'/api/report/{exp_id}/json')
        self.assertEqual(res_exp.status_code, 200)
        report_data = json.loads(res_exp.data)
        self.assertEqual(report_data['experiment_id'], exp_id)
        self.assertIn('decision', report_data)

    def test_invalid_endpoint_error(self):
        """invalid endpoint produces a friendly error"""
        res = self.client.post('/api/test_ai/start', json={
            "baseline_endpoint": "",
            "candidate_endpoint": "",
            "provider": "http",
            "size": "QUICK"
        })
        if res.status_code != 400:
            print("ERROR in test_ai start:", res.data)
        self.assertEqual(res.status_code, 400)
        data = json.loads(res.data)
        self.assertEqual(data["error"], "Missing endpoints")

if __name__ == '__main__':
    unittest.main()
