import os
import json
import hashlib
from typing import List, Dict, Tuple, Any
from core.schema import TestSpec

class CorpusManager:
    def __init__(self, corpus_dir: str = "tests"):
        self.corpus_dir = corpus_dir
        self.tests: Dict[str, TestSpec] = {}
        self._load_corpus()

    def _load_corpus(self):
        if not os.path.exists(self.corpus_dir):
            return

        for root, _, files in os.walk(self.corpus_dir):
            for file in files:
                if file.endswith(".json"):
                    filepath = os.path.join(root, file)
                    try:
                        spec = self.load_test_file(filepath)
                        if spec.test_id in self.tests:
                            print(f"WARNING: Duplicate test_id '{spec.test_id}' found in {filepath}. Overwriting.")
                        self.tests[spec.test_id] = spec
                    except Exception as e:
                        print(f"Error loading {filepath}: {e}")

    def load_test_file(self, filepath: str) -> TestSpec:
        with open(filepath, 'r') as f:
            data = json.load(f)



        content_for_hash = {k: v for k, v in data.items() if k not in ("test_version", "status")}
        content_hash = hashlib.sha256(json.dumps(content_for_hash, sort_keys=True).encode()).hexdigest()[:8]





        from core.schema import TurnSpec, EvaluationCriterion
        turns = []
        for t in data.get("turns", []):
            criteria = [EvaluationCriterion(**c) for c in t.get("criteria", [])]
            turns.append(TurnSpec(
                user_input=t.get("user") or t.get("user_input"),
                criteria=criteria,
                expected_behavior=t.get("expected_behavior", "")
            ))
        if turns:
            data["turns"] = turns

        if "criteria" in data and isinstance(data["criteria"], list) and len(data["criteria"]) > 0:
            if isinstance(data["criteria"][0], dict):
                data["criteria"] = [EvaluationCriterion(**c) for c in data["criteria"]]

        return TestSpec(**data)

    def get_valid_tests(self) -> List[TestSpec]:

        return [t for t in self.tests.values() if t.status.upper() == "VALID"]

    def get_tests_by_domain(self, domain: str) -> List[TestSpec]:
        return [t for t in self.tests.values() if t.domain.lower() == domain.lower()]

    def compute_coverage(self) -> Dict[str, Any]:

        coverage = {
            "total_tests": len(self.tests),
            "status": {},
            "domains": {},
            "principles": {},
            "tags": {}
        }

        for t in self.tests.values():

            stat = t.status.upper()
            coverage["status"][stat] = coverage["status"].get(stat, 0) + 1


            dom = t.domain.lower()
            coverage["domains"][dom] = coverage["domains"].get(dom, 0) + 1


            for p in t.principles:
                p = p.lower()
                coverage["principles"][p] = coverage["principles"].get(p, 0) + 1


            for tag in t.tags:
                tag = tag.lower()
                coverage["tags"][tag] = coverage["tags"].get(tag, 0) + 1

        return coverage

    def print_coverage_report(self):
        cov = self.compute_coverage()
        print("=" * 50)
        print("CORPUS COVERAGE REPORT")
        print("=" * 50)
        print(f"Total Tests: {cov['total_tests']}")

        print("\n--- Status ---")
        for k, v in sorted(cov["status"].items(), key=lambda x: x[1], reverse=True):
            print(f"{k.ljust(25)} {v}")

        print("\n--- Domains ---")
        for k, v in sorted(cov["domains"].items(), key=lambda x: x[1], reverse=True):
            print(f"{k.ljust(25)} {v}")

        print("\n--- Principles ---")
        for k, v in sorted(cov["principles"].items(), key=lambda x: x[1], reverse=True):
            print(f"{k.ljust(25)} {v}")

        print("\n--- Behavioral Tags ---")
        for k, v in sorted(cov["tags"].items(), key=lambda x: x[1], reverse=True):
            print(f"{k.ljust(25)} {v}")
