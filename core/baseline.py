import os
import json
import sqlite3
import dataclasses
from typing import List, Dict, Any, Optional

from database.sqlite import DB_PATH, get_test_result, get_session_result

BASELINE_DIR = "baselines"

@dataclasses.dataclass
class BaselineManifest:
    name: str
    timestamp: float
    metadata: Dict[str, Any]
    test_runs: List[str]
    session_runs: List[str]

def create_baseline(name: str, provider: str = None):
    if not os.path.exists(BASELINE_DIR):
        os.makedirs(BASELINE_DIR)

    target_dir = os.path.join(BASELINE_DIR, name)
    if os.path.exists(target_dir):
        print(f"Baseline '{name}' already exists.")
        return

    os.makedirs(target_dir)
    runs_dir = os.path.join(target_dir, "runs")
    os.makedirs(runs_dir)



    run_ids = []
    session_ids = []

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()


        if provider:

            query = """
                SELECT run_id FROM test_runs
                WHERE json_extract(metadata_json, '$.provider') = ?
                GROUP BY test_id HAVING max(timestamp)
            """
            cursor.execute(query, (provider,))
        else:
            query = "SELECT run_id FROM test_runs GROUP BY test_id HAVING max(timestamp)"
            cursor.execute(query)

        run_ids = [row[0] for row in cursor.fetchall()]


        if provider:
            query = """
                SELECT session_id FROM test_sessions
                WHERE json_extract(metadata_json, '$.provider') = ?
                GROUP BY test_id HAVING max(timestamp)
            """
            cursor.execute(query, (provider,))
        else:
            query = "SELECT session_id FROM test_sessions GROUP BY test_id HAVING max(timestamp)"
            cursor.execute(query)

        session_ids = [row[0] for row in cursor.fetchall()]


    baseline_metadata = {}

    for rid in run_ids:
        res = get_test_result(rid)
        if res:
            if not baseline_metadata:
                baseline_metadata = dataclasses.asdict(res.metadata)

            with open(os.path.join(runs_dir, f"run_{rid}.json"), "w") as f:
                json.dump(dataclasses.asdict(res), f, indent=2)

    for sid in session_ids:
        res = get_session_result(sid)
        if res:
            if not baseline_metadata:
                baseline_metadata = dataclasses.asdict(res.metadata)

            with open(os.path.join(runs_dir, f"session_{sid}.json"), "w") as f:
                json.dump(dataclasses.asdict(res), f, indent=2)

    import time
    manifest = BaselineManifest(
        name=name,
        timestamp=time.time(),
        metadata=baseline_metadata,
        test_runs=run_ids,
        session_runs=session_ids
    )

    with open(os.path.join(target_dir, "manifest.json"), "w") as f:
        json.dump(dataclasses.asdict(manifest), f, indent=2)

    with open(os.path.join(target_dir, "README.md"), "w") as f:
        f.write(f"# Baseline: {name}\n\n")
        f.write(f"Frozen on: {time.ctime(manifest.timestamp)}\n")
        f.write(f"Test Runs: {len(run_ids)}\n")
        f.write(f"Sessions: {len(session_ids)}\n")

    print(f"Created baseline '{name}' with {len(run_ids)} single-turn tests and {len(session_ids)} sessions.")

def load_baseline(name: str):
    target_dir = os.path.join(BASELINE_DIR, name)
    if not os.path.exists(target_dir):
        raise ValueError(f"Baseline '{name}' not found.")

    with open(os.path.join(target_dir, "manifest.json"), "r") as f:
        manifest_data = json.load(f)

    manifest = BaselineManifest(**manifest_data)

    runs = []
    sessions = []


    from core.schema import TestResult, SessionResult, ExecutionMetadata, EvaluationResult, EvaluationFailure, LayerEvaluation, LayerVerdict, TurnResult




    runs_dir = os.path.join(target_dir, "runs")
    for rid in manifest.test_runs:
        with open(os.path.join(runs_dir, f"run_{rid}.json"), "r") as f:
            runs.append(json.load(f))

    for sid in manifest.session_runs:
        with open(os.path.join(runs_dir, f"session_{sid}.json"), "r") as f:
            sessions.append(json.load(f))

    return manifest, runs, sessions
