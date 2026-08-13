import sqlite3
import json
import dataclasses
from typing import List, Optional, Any
from core.schema import TestResult, EvaluationResult, EvaluationFailure, ExecutionMetadata, LayerEvaluation, LayerVerdict

DB_PATH = "behave.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_runs (
                run_id TEXT PRIMARY KEY,
                test_id TEXT,
                test_version TEXT,
                ai_response TEXT,
                auto_passed BOOLEAN,
                score REAL,
                failures_json TEXT,
                reasoning TEXT,
                timestamp REAL,
                human_verdict TEXT,
                human_reason TEXT,
                review_timestamp REAL,
                metadata_json TEXT,
                layer_evaluations_json TEXT
            )
        ''')
        conn.commit()

def save_test_result(result: TestResult):
    init_db()
    
    failures_json = json.dumps([{
        "tags": f.tags,
        "root_cause": f.root_cause,
        "observed_behavior": f.observed_behavior,
        "expected_behavior": f.expected_behavior,
        "severity": f.severity
    } for f in result.evaluation.failures])
    
    metadata_json = json.dumps(dataclasses.asdict(result.metadata))
    layer_evaluations_json = json.dumps([dataclasses.asdict(l) for l in result.evaluation.layer_evaluations])
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # We might be dealing with an old database schema that doesn't have the new columns.
        try:
            cursor.execute('ALTER TABLE test_runs ADD COLUMN test_version TEXT')
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute('ALTER TABLE test_runs ADD COLUMN metadata_json TEXT')
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute('ALTER TABLE test_runs ADD COLUMN layer_evaluations_json TEXT')
        except sqlite3.OperationalError:
            pass

        cursor.execute('''
            INSERT INTO test_runs (
                run_id, test_id, test_version, ai_response, auto_passed, score,
                failures_json, reasoning, timestamp,
                human_verdict, human_reason, review_timestamp, metadata_json, layer_evaluations_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            result.run_id,
            result.test_id,
            result.test_version,
            result.ai_response,
            result.evaluation.passed,
            result.evaluation.score,
            failures_json,
            result.evaluation.reasoning,
            result.timestamp,
            result.evaluation.human_verdict,
            result.evaluation.human_reason,
            result.evaluation.review_timestamp,
            metadata_json,
            layer_evaluations_json
        ))
        conn.commit()

def update_human_override(run_id: str, verdict: str, reason: str, timestamp: float):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE test_runs 
            SET human_verdict = ?, human_reason = ?, review_timestamp = ?
            WHERE run_id = ?
        ''', (verdict, reason, timestamp, run_id))
        conn.commit()

def get_test_result(run_id: str) -> Optional[TestResult]:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        # Handle columns that might not exist in old schemas by selecting * and parsing manually or just fetching safe columns
        # To be completely safe with backward compat:
        cursor.execute('PRAGMA table_info(test_runs)')
        columns = [info[1] for info in cursor.fetchall()]
        
        cursor.execute(f'''
            SELECT * FROM test_runs WHERE run_id = ?
        ''', (run_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
            
        row_dict = dict(zip(columns, row))
        
        test_id = row_dict.get("test_id", "unknown")
        test_version = row_dict.get("test_version", "unknown")
        ai_response = row_dict.get("ai_response", "")
        auto_passed = row_dict.get("auto_passed", False)
        score = row_dict.get("score", 0.0)
        failures_json = row_dict.get("failures_json", "[]")
        reasoning = row_dict.get("reasoning", "")
        timestamp = row_dict.get("timestamp", 0.0)
        human_verdict = row_dict.get("human_verdict", None)
        human_reason = row_dict.get("human_reason", None)
        review_timestamp = row_dict.get("review_timestamp", None)
        metadata_json = row_dict.get("metadata_json", None)
        layer_evaluations_json = row_dict.get("layer_evaluations_json") or "[]"
        
        failures_data = json.loads(failures_json)
        failures = []
        for f in failures_data:
            # Backward compatibility with Phase 1
            if "category" in f:
                f["tags"] = [f.pop("category")]
                f["root_cause"] = "unknown"
            failures.append(EvaluationFailure(**f))
            
        layers_data = json.loads(layer_evaluations_json)
        layer_evals = []
        for ld in layers_data:
            layer_failures = []
            for f in ld.get("failures", []):
                # Backward compatibility with Phase 1
                if "category" in f:
                    f["tags"] = [f.pop("category")]
                    f["root_cause"] = "unknown"
                layer_failures.append(EvaluationFailure(**f))
            
            # Map back enum
            verdict_str = ld.get("verdict")
            verdict = LayerVerdict(verdict_str) if verdict_str else LayerVerdict.UNCERTAIN
            
            layer_evals.append(LayerEvaluation(
                layer_name=ld.get("layer_name", "unknown"),
                verdict=verdict,
                failures=layer_failures,
                reasoning=ld.get("reasoning", ""),
                confidence=ld.get("confidence", None),
                criteria_results=ld.get("criteria_results", {})
            ))
        
        evaluation = EvaluationResult(
            passed=bool(auto_passed),
            score=score,
            failures=failures,
            reasoning=reasoning,
            layer_evaluations=layer_evals,
            human_verdict=human_verdict,
            human_reason=human_reason,
            review_timestamp=review_timestamp
        )
        
        metadata = ExecutionMetadata()
        if metadata_json:
            metadata_dict = json.loads(metadata_json)
            metadata = ExecutionMetadata(**metadata_dict)
        
        return TestResult(
            run_id=run_id,
            test_id=test_id,
            test_version=test_version,
            ai_response=ai_response,
            evaluation=evaluation,
            metadata=metadata,
            timestamp=timestamp
        )
