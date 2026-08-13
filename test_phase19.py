import os
import unittest
import json
import shutil
from app import app
from core.experiment_registry import REGISTRY_DIR
from database.sqlite import init_db, DB_PATH

class TestPhase19(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        
        if os.path.exists(REGISTRY_DIR):
            shutil.rmtree(REGISTRY_DIR)
        os.makedirs(REGISTRY_DIR)
        
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        init_db()

    def tearDown(self):
        if os.path.exists(REGISTRY_DIR):
            shutil.rmtree(REGISTRY_DIR)
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)

    def test_api_experiments_crud(self):
        # Create experiment
        payload = {
            "hypothesis": "Test phase 19",
            "baseline": "v1",
            "candidate": "v2",
            "budget": 5.0
        }
        res = self.app.post("/api/experiments", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertIn("exp_", data["experiment_id"])
        self.assertEqual(data["hypothesis"], "Test phase 19")
        
        exp_id = data["experiment_id"]
        
        # Get experiment
        res2 = self.app.get(f"/api/experiments/{exp_id}")
        self.assertEqual(res2.status_code, 200)
        data2 = res2.get_json()
        self.assertEqual(data2["experiment_id"], exp_id)
        
        # List experiments
        res3 = self.app.get("/api/experiments")
        self.assertEqual(res3.status_code, 200)
        data3 = res3.get_json()
        self.assertEqual(len(data3), 1)
        self.assertEqual(data3[0]["experiment_id"], exp_id)
        
    def test_api_run_missing_baselines(self):
        payload = {
            "hypothesis": "Run test",
            "baseline": "nonexistent1",
            "candidate": "nonexistent2",
            "budget": 5.0
        }
        res = self.app.post("/api/experiments", json=payload)
        exp_id = res.get_json()["experiment_id"]
        
        res2 = self.app.post(f"/api/experiments/{exp_id}/run")
        self.assertEqual(res2.status_code, 400)
        self.assertIn("error", res2.get_json())
        
        # Check status was updated to FAILED
        res3 = self.app.get(f"/api/experiments/{exp_id}")
        self.assertEqual(res3.get_json()["status"], "FAILED")
        
    def test_api_tests(self):
        res = self.app.get("/api/tests")
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.get_json(), list)

    def test_api_reliability(self):
        res = self.app.get("/api/reliability")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("total_evaluations", data)

if __name__ == '__main__':
    unittest.main()
