import os
import unittest
import time
import sqlite3
import json
from core.schema import TestSpec, TestResult, EvaluationResult, EvaluationFailure, ExecutionMetadata
from core.test_runner import TestRunner
from core.evaluator import Evaluator
from models.mock import MockAIModel
from models.provider import ProviderConfig
from core.metadata import sanitize_config, hash_dict, hash_string, get_git_info
from database.sqlite import init_db, save_test_result, get_test_result, DB_PATH, update_human_override

class TestPhase3(unittest.TestCase):
    def setUp(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        init_db()
        config = ProviderConfig(provider_name="mock", model_name="mock-v1")
        self.ai_model = MockAIModel(config=config)
        self.evaluator = Evaluator()
        self.runner = TestRunner(provider=self.ai_model, evaluator=self.evaluator)

        self.spec = TestSpec(
            test_id="test_003",
            test_version="v1.2",
            scenario="Test scenario"
        )

    def tearDown(self):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)

    def test_run_id_uniqueness(self):
        result1 = self.runner.run_test(self.spec)
        result2 = self.runner.run_test(self.spec)


        self.assertNotEqual(result1.run_id, result2.run_id)
        self.assertEqual(result1.test_id, result2.test_id)
        self.assertEqual(result1.test_version, result2.test_version)

    def test_git_metadata_and_hashing(self):
        result = self.runner.run_test(self.spec)
        save_test_result(result)

        retrieved = get_test_result(result.run_id)


        self.assertIsNotNone(retrieved.metadata.git_commit)
        self.assertIsInstance(retrieved.metadata.git_dirty, bool)


        dummy1 = {"temp": 0.7}
        dummy2 = {"temp": 0.7}
        self.assertEqual(hash_dict(dummy1), hash_dict(dummy2))


        self.assertEqual(retrieved.metadata.system_prompt_hash, result.metadata.system_prompt_hash)
        self.assertEqual(retrieved.metadata.configuration_hash, result.metadata.configuration_hash)

    def test_secret_sanitization(self):

        conf_with_secret = {"temp": 0.5, "GEMINI_API_KEY": "sk-real-secret"}
        conf_without_secret = {"temp": 0.5, "GEMINI_API_KEY": "sk-other-secret"}


        self.assertEqual(hash_dict(conf_with_secret), hash_dict(conf_without_secret))

    def test_legacy_data_handling(self):

        eval_res = EvaluationResult(passed=True, score=100.0)
        old_test = TestResult(
            run_id="old_123",
            test_id="old_test",
            test_version="unknown",
            ai_response="success",
            evaluation=eval_res,
            metadata=ExecutionMetadata(),
            timestamp=time.time()
        )
        save_test_result(old_test)

        update_human_override("old_123", "FAIL", "overridden", time.time())
        retrieved = get_test_result("old_123")
        self.assertEqual(retrieved.evaluation.human_verdict, "FAIL")


        self.assertEqual(retrieved.test_version, "unknown")
        self.assertEqual(retrieved.metadata.provider, "unknown")

if __name__ == '__main__':
    unittest.main()
