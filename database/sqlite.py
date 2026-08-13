import sqlite3
import json
from typing import List, Optional
from core.schema import TestResult, EvaluationResult, EvaluationFailure

DB_PATH = "behave.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_runs (
                run_id TEXT PRIMARY KEY,
                test_id TEXT,
                ai_response TEXT,
                auto_passed BOOLEAN,
                score REAL,
                failures_json TEXT,
                reasoning TEXT,
                timestamp REAL,
                human_verdict TEXT,
                human_reason TEXT,
                review_timestamp REAL
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
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO test_runs (
                run_id, test_id, ai_response, auto_passed, score,
                failures_json, reasoning, timestamp,
                human_verdict, human_reason, review_timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            result.run_id,
            result.test_id,
            result.ai_response,
            result.evaluation.passed,
            result.evaluation.score,
            failures_json,
            result.evaluation.reasoning,
            result.timestamp,
            result.evaluation.human_verdict,
            result.evaluation.human_reason,
            result.evaluation.review_timestamp
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
        cursor.execute('''
            SELECT test_id, ai_response, auto_passed, score, failures_json,
                   reasoning, timestamp, human_verdict, human_reason, review_timestamp
            FROM test_runs WHERE run_id = ?
        ''', (run_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
            
        test_id, ai_response, auto_passed, score, failures_json, reasoning, timestamp, human_verdict, human_reason, review_timestamp = row
        
        failures_data = json.loads(failures_json)
        failures = []
        for f in failures_data:
            # Backward compatibility with Phase 1
            if "category" in f:
                f["tags"] = [f.pop("category")]
                f["root_cause"] = "unknown"
            failures.append(EvaluationFailure(**f))
        
        evaluation = EvaluationResult(
            passed=bool(auto_passed),
            score=score,
            failures=failures,
            reasoning=reasoning,
            human_verdict=human_verdict,
            human_reason=human_reason,
            review_timestamp=review_timestamp
        )
        
        return TestResult(
            run_id=run_id,
            test_id=test_id,
            ai_response=ai_response,
            evaluation=evaluation,
            timestamp=timestamp
        )
