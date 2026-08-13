import sqlite3
import json
import dataclasses
from typing import List, Optional, Any
from core.schema import TestResult, EvaluationResult, EvaluationFailure, ExecutionMetadata, LayerEvaluation, LayerVerdict, SessionResult, TurnResult

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
                layer_evaluations_json TEXT,
                usage_json TEXT,
                provider_status TEXT,
                attempt_number INTEGER
            )
        ''')
        
        # Phase 8 Stateful schemas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_sessions (
                session_id TEXT PRIMARY KEY,
                test_id TEXT,
                test_version TEXT,
                final_evaluation_json TEXT,
                metadata_json TEXT,
                timestamp REAL,
                usage_json TEXT,
                provider_status TEXT,
                attempt_number INTEGER
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_turns (
                turn_id TEXT PRIMARY KEY,
                session_id TEXT,
                turn_number INTEGER,
                user_input TEXT,
                ai_response TEXT,
                evaluation_json TEXT,
                timestamp REAL,
                human_verdict TEXT,
                human_reason TEXT,
                review_timestamp REAL,
                usage_json TEXT,
                provider_status TEXT,
                attempt_number INTEGER,
                FOREIGN KEY(session_id) REFERENCES test_sessions(session_id)
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
        try:
            cursor.execute('ALTER TABLE test_runs ADD COLUMN usage_json TEXT')
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute('ALTER TABLE test_runs ADD COLUMN provider_status TEXT')
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute('ALTER TABLE test_runs ADD COLUMN attempt_number INTEGER')
        except sqlite3.OperationalError:
            pass

        cursor.execute('''
            INSERT INTO test_runs (
                run_id, test_id, test_version, ai_response, auto_passed, score,
                failures_json, reasoning, timestamp,
                human_verdict, human_reason, review_timestamp, metadata_json, layer_evaluations_json,
                usage_json, provider_status, attempt_number
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            layer_evaluations_json,
            json.dumps(result.usage_json),
            result.provider_status,
            result.attempt_number
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
        usage_json = row_dict.get("usage_json", "{}")
        provider_status = row_dict.get("provider_status", "SUCCESS")
        attempt_number = row_dict.get("attempt_number", 1)
        
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
                criteria_results=ld.get("criteria_results", {}),
                metadata=ld.get("metadata", {})
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
            timestamp=timestamp,
            usage_json=json.loads(usage_json) if usage_json and usage_json.strip() else {},
            provider_status=provider_status,
            attempt_number=attempt_number
        )

def _serialize_evaluation(evaluation: EvaluationResult) -> str:
    failures = [{
        "tags": f.tags,
        "root_cause": f.root_cause,
        "observed_behavior": f.observed_behavior,
        "expected_behavior": f.expected_behavior,
        "severity": f.severity,
        "is_critical": f.is_critical
    } for f in evaluation.failures]
    layer_evaluations = [dataclasses.asdict(l) for l in evaluation.layer_evaluations]
    return json.dumps({
        "passed": evaluation.passed,
        "score": evaluation.score,
        "failures": failures,
        "reasoning": evaluation.reasoning,
        "layer_evaluations": layer_evaluations,
        "trajectory": evaluation.trajectory,
        "evidence_timeline": evaluation.evidence_timeline,
        "critical_failure": evaluation.critical_failure,
        "critical_failure_count": evaluation.critical_failure_count,
        "severity_counts": evaluation.severity_counts,
        "score_breakdown": evaluation.score_breakdown,
        "session_metadata": evaluation.session_metadata,
        "human_verdict": evaluation.human_verdict,
        "human_reason": evaluation.human_reason,
        "review_timestamp": evaluation.review_timestamp
    })

def _deserialize_evaluation(json_str: str) -> EvaluationResult:
    if not json_str:
        return EvaluationResult(passed=False, score=0.0)
    data = json.loads(json_str)
    
    failures = []
    for f in data.get("failures", []):
        failures.append(EvaluationFailure(**f))
        
    layer_evals = []
    for ld in data.get("layer_evaluations", []):
        layer_failures = [EvaluationFailure(**f) for f in ld.get("failures", [])]
        verdict_str = ld.get("verdict")
        verdict = LayerVerdict(verdict_str) if verdict_str else LayerVerdict.UNCERTAIN
        layer_evals.append(LayerEvaluation(
            layer_name=ld.get("layer_name", "unknown"),
            verdict=verdict,
            failures=layer_failures,
            reasoning=ld.get("reasoning", ""),
            confidence=ld.get("confidence", None),
            criteria_results=ld.get("criteria_results", {}),
            metadata=ld.get("metadata", {})
        ))
        
    return EvaluationResult(
        passed=data.get("passed", False),
        score=data.get("score", 0.0),
        failures=failures,
        reasoning=data.get("reasoning", ""),
        layer_evaluations=layer_evals,
        trajectory=data.get("trajectory"),
        evidence_timeline=data.get("evidence_timeline", []),
        critical_failure=data.get("critical_failure", False),
        critical_failure_count=data.get("critical_failure_count", 0),
        severity_counts=data.get("severity_counts", {}),
        score_breakdown=data.get("score_breakdown", {}),
        session_metadata=data.get("session_metadata", {}),
        human_verdict=data.get("human_verdict"),
        human_reason=data.get("human_reason"),
        review_timestamp=data.get("review_timestamp")
    )

def save_session_result(session: SessionResult):
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO test_sessions (
                session_id, test_id, test_version, final_evaluation_json, metadata_json, timestamp,
                usage_json, provider_status, attempt_number
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            session.session_id,
            session.test_id,
            session.test_version,
            _serialize_evaluation(session.final_evaluation),
            json.dumps(dataclasses.asdict(session.metadata)),
            session.timestamp,
            json.dumps(session.usage_json),
            session.provider_status,
            session.attempt_number
        ))
        
        for turn in session.turns:
            cursor.execute('''
                INSERT INTO test_turns (
                    turn_id, session_id, turn_number, user_input, ai_response,
                    evaluation_json, timestamp, human_verdict, human_reason, review_timestamp,
                    usage_json, provider_status, attempt_number
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                turn.turn_id,
                session.session_id,
                turn.turn_number,
                turn.user_input,
                turn.ai_response,
                _serialize_evaluation(turn.evaluation),
                turn.timestamp,
                turn.evaluation.human_verdict,
                turn.evaluation.human_reason,
                turn.evaluation.review_timestamp,
                json.dumps(turn.usage_json),
                turn.provider_status,
                turn.attempt_number
            ))
        conn.commit()

def get_session_result(session_id: str) -> Optional[SessionResult]:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM test_sessions WHERE session_id = ?', (session_id,))
        s_row = cursor.fetchone()
        if not s_row:
            return None
        
        cursor.execute('PRAGMA table_info(test_sessions)')
        s_cols = [info[1] for info in cursor.fetchall()]
        s_dict = dict(zip(s_cols, s_row))
        
        cursor.execute('SELECT * FROM test_turns WHERE session_id = ? ORDER BY turn_number ASC', (session_id,))
        t_rows = cursor.fetchall()
        cursor.execute('PRAGMA table_info(test_turns)')
        t_cols = [info[1] for info in cursor.fetchall()]
        
        turns = []
        for t_row in t_rows:
            t_dict = dict(zip(t_cols, t_row))
            turn_eval = _deserialize_evaluation(t_dict.get("evaluation_json", "{}"))
            # Hydrate human overrides directly onto the turn's evaluation
            turn_eval.human_verdict = t_dict.get("human_verdict")
            turn_eval.human_reason = t_dict.get("human_reason")
            turn_eval.review_timestamp = t_dict.get("review_timestamp")
            
            turns.append(TurnResult(
                turn_id=t_dict["turn_id"],
                turn_number=t_dict["turn_number"],
                user_input=t_dict.get("user_input", ""),
                ai_response=t_dict.get("ai_response", ""),
                evaluation=turn_eval,
                timestamp=t_dict.get("timestamp", 0.0),
                usage_json=json.loads(t_dict.get("usage_json", "{}")) if t_dict.get("usage_json") else {},
                provider_status=t_dict.get("provider_status", "SUCCESS"),
                attempt_number=t_dict.get("attempt_number", 1)
            ))
            
        meta = ExecutionMetadata()
        if s_dict.get("metadata_json"):
            meta = ExecutionMetadata(**json.loads(s_dict["metadata_json"]))
            
        return SessionResult(
            session_id=s_dict["session_id"],
            test_id=s_dict.get("test_id", "unknown"),
            test_version=s_dict.get("test_version", "unknown"),
            turns=turns,
            final_evaluation=_deserialize_evaluation(s_dict.get("final_evaluation_json", "{}")),
            metadata=meta,
            timestamp=s_dict.get("timestamp", 0.0),
            usage_json=json.loads(s_dict.get("usage_json", "{}")) if s_dict.get("usage_json") else {},
            provider_status=s_dict.get("provider_status", "SUCCESS"),
            attempt_number=s_dict.get("attempt_number", 1)
        )
