import os
import unittest
import json
import shutil
from typing import Any

from core.schema import TestSpec
from core.corpus import CorpusManager

class TestPhase13(unittest.TestCase):
    def setUp(self):
        self.test_dir = "temp_tests"
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def _create_test_file(self, filename: str, content: dict):
        with open(os.path.join(self.test_dir, filename), "w") as f:
            json.dump(content, f, indent=2)

    def test_corpus_loading_and_validity(self):

        self._create_test_file("t1.json", {
            "test_id": "t1",
            "scenario": "test 1",
            "test_version": "1.0",
            "domain": "reasoning",
            "status": "VALID",
            "principles": ["avoid_premature_conclusions"]
        })
        self._create_test_file("t2.json", {
            "test_id": "t2",
            "scenario": "test 2",
            "test_version": "1.1",
            "domain": "reasoning",
            "status": "DEPRECATED"
        })
        self._create_test_file("t3.json", {
            "test_id": "t3",
            "scenario": "test 3",
            "test_version": "2.0",
            "domain": "diagnostics",
            "status": "VALID",
            "tags": ["hallucination"]
        })

        manager = CorpusManager(corpus_dir=self.test_dir)


        self.assertEqual(len(manager.tests), 3)


        valid = manager.get_valid_tests()
        self.assertEqual(len(valid), 2)
        self.assertEqual(set(t.test_id for t in valid), {"t1", "t3"})


        reasoning_tests = manager.get_tests_by_domain("reasoning")
        self.assertEqual(len(reasoning_tests), 2)

    def test_coverage_tracking(self):

        self._create_test_file("t1.json", {
            "test_id": "t1",
            "scenario": "test 1",
            "domain": "reasoning",
            "status": "VALID",
            "principles": ["p1", "p2"],
            "tags": ["tag1"]
        })
        self._create_test_file("t2.json", {
            "test_id": "t2",
            "scenario": "test 2",
            "domain": "diagnostics",
            "status": "VALID",
            "principles": ["p2"],
            "tags": ["tag1", "tag2"]
        })
        self._create_test_file("t3.json", {
            "test_id": "t3",
            "scenario": "test 3",
            "domain": "reasoning",
            "status": "EXPERIMENTAL",
            "principles": ["p3"]
        })

        manager = CorpusManager(corpus_dir=self.test_dir)
        cov = manager.compute_coverage()

        self.assertEqual(cov["total_tests"], 3)
        self.assertEqual(cov["status"]["VALID"], 2)
        self.assertEqual(cov["status"]["EXPERIMENTAL"], 1)
        self.assertEqual(cov["domains"]["reasoning"], 2)
        self.assertEqual(cov["domains"]["diagnostics"], 1)
        self.assertEqual(cov["principles"]["p2"], 2)
        self.assertEqual(cov["tags"]["tag1"], 2)

if __name__ == '__main__':
    unittest.main()
