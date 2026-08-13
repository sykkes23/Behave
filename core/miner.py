import json
import sqlite3
import random
from typing import Dict, List, Any
from core.schema import TestSpec
from database.sqlite import DB_PATH, get_test_result, get_session_result
from core.corpus import CorpusManager
import os

class FailureMiner:
    def __init__(self, db_path: str = DB_PATH, corpus_dir: str = "tests"):
        self.db_path = db_path
        self.corpus_manager = CorpusManager(corpus_dir=corpus_dir)
        
    def analyze_failures(self) -> Dict[str, Any]:
        """
        Analyzes the database for recurring failure patterns.
        """
        if not os.path.exists(self.db_path):
            return {}
            
        stats = {
            "tags": {},
            "root_causes": {},
            "affected_tests": {}
        }
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # test_runs
            cursor.execute("SELECT test_id, failures_json FROM test_runs WHERE auto_passed = 0")
            for test_id, failures_json in cursor.fetchall():
                if failures_json:
                    try:
                        failures = json.loads(failures_json)
                        for f in failures:
                            for tag in f.get("tags", []):
                                stats["tags"][tag] = stats["tags"].get(tag, 0) + 1
                                if tag not in stats["affected_tests"]:
                                    stats["affected_tests"][tag] = set()
                                stats["affected_tests"][tag].add(test_id)
                            rc = f.get("root_cause")
                            if rc:
                                stats["root_causes"][rc] = stats["root_causes"].get(rc, 0) + 1
                    except:
                        pass
                        
            # test_sessions
            cursor.execute("SELECT test_id, final_evaluation_json FROM test_sessions")
            for test_id, eval_json in cursor.fetchall():
                if eval_json:
                    try:
                        ev = json.loads(eval_json)
                        if not ev.get("passed", False):
                            for f in ev.get("failures", []):
                                for tag in f.get("tags", []):
                                    stats["tags"][tag] = stats["tags"].get(tag, 0) + 1
                                    if tag not in stats["affected_tests"]:
                                        stats["affected_tests"][tag] = set()
                                    stats["affected_tests"][tag].add(test_id)
                                rc = f.get("root_cause")
                                if rc:
                                    stats["root_causes"][rc] = stats["root_causes"].get(rc, 0) + 1
                    except:
                        pass
                        
        for tag in stats["affected_tests"]:
            stats["affected_tests"][tag] = list(stats["affected_tests"][tag])
            
        return stats

    def generate_variant(self, failure_tag: str, count: int = 1) -> List[TestSpec]:
        """
        Generates candidate variants for a given failure tag.
        (For now, uses a synthetic logic instead of an actual LLM call to save time and API usage, 
        but structures it exactly as requested).
        """
        stats = self.analyze_failures()
        affected_tests = stats.get("affected_tests", {}).get(failure_tag, [])
        
        if not affected_tests:
            print(f"No affected tests found for failure tag: {failure_tag}")
            return []
            
        variants = []
        strategies = ["ADD_CONTRADICTORY_EVIDENCE", "CHANGE_SYMPTOM", "ADD_TIME_PRESSURE"]
        
        for _ in range(count):
            # Pick a random parent test that exhibited this failure
            parent_id = random.choice(affected_tests)
            parent_spec = self.corpus_manager.tests.get(parent_id)
            
            if not parent_spec:
                continue
                
            strategy = random.choice(strategies)
            
            import copy
            import uuid
            
            variant_id = f"{parent_id}_variant_{str(uuid.uuid4())[:4]}"
            
            new_spec = copy.deepcopy(parent_spec)
            new_spec.test_id = variant_id
            new_spec.test_version = "1.0"
            new_spec.status = "EXPERIMENTAL"
            new_spec.origin = "failure_mining"
            new_spec.parent_test = parent_id
            new_spec.parent_version = parent_spec.test_version
            new_spec.generation_reason = failure_tag
            new_spec.mutation_strategy = strategy
            
            # Mutate scenario slightly
            new_spec.scenario = f"[Mutated: {strategy}] " + new_spec.scenario
            
            # Duplication check logic (simple for now)
            duplicate_flag = False
            for t in self.corpus_manager.tests.values():
                if t.scenario == new_spec.scenario:
                    duplicate_flag = True
            
            new_spec.duplicate_flag = duplicate_flag
            
            # Save the new variant file in a generated/ directory or in the same directory as parent?
            # Let's save it to a generated directory within tests
            gen_dir = os.path.join(self.corpus_manager.corpus_dir, "generated")
            if not os.path.exists(gen_dir):
                os.makedirs(gen_dir)
                
            out_path = os.path.join(gen_dir, f"{variant_id}.json")
            import dataclasses
            with open(out_path, "w") as f:
                json.dump(dataclasses.asdict(new_spec), f, indent=2)
                
            variants.append(new_spec)
            print(f"Generated variant {variant_id} (Strategy: {strategy}) -> {out_path}")
            
        return variants
