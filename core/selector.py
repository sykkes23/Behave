import os
import json
import sqlite3
import random
import hashlib
from typing import List, Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass, field

from core.schema import TestSpec
from database.sqlite import DB_PATH
from core.corpus import CorpusManager

class SelectionStrategy(str, Enum):
    FULL = "FULL"
    RANDOM = "RANDOM"
    FAILURE_FOCUSED = "FAILURE_FOCUSED"
    REGRESSION_FOCUSED = "REGRESSION_FOCUSED"
    RISK_FOCUSED = "RISK_FOCUSED"
    NOVELTY_FOCUSED = "NOVELTY_FOCUSED"
    BALANCED = "BALANCED"

@dataclass
class SelectedTest:
    test_id: str
    test_version: str
    priority_score: float
    reasons: List[str]

@dataclass
class SelectionManifest:
    experiment_id: str
    strategy: str
    seed: int
    selector_version: str
    selection_policy_hash: str
    provider: str
    selected_tests: List[SelectedTest]
    unselected_tests: int
    coverage_warnings: List[str]

class TestSelector:
    __test__ = False

    def __init__(self, db_path: str = DB_PATH, corpus_dir: str = "tests"):
        self.db_path = db_path
        self.corpus_manager = CorpusManager(corpus_dir=corpus_dir)
        self.selector_version = "1.0.0"

    def _fetch_history(self, provider: str = None) -> Dict[str, Dict[str, Any]]:
        history = {}
        if not os.path.exists(self.db_path):
            return history

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()


            query = "SELECT test_id, auto_passed, failures_json, usage_json, metadata_json, timestamp FROM test_runs"
            if provider:
                query += " WHERE json_extract(metadata_json, '$.provider') = ?"
                cursor.execute(query, (provider,))
            else:
                cursor.execute(query)

            for tid, auto_passed, fails, usage, meta, ts in cursor.fetchall():
                if tid not in history:
                    history[tid] = {"runs": 0, "fails": 0, "criticals": 0, "last_ts": 0, "avg_cost": 0.0, "cost_samples": 0}

                history[tid]["runs"] += 1
                if not auto_passed:
                    history[tid]["fails"] += 1
                if ts > history[tid]["last_ts"]:
                    history[tid]["last_ts"] = ts

                if fails:
                    try:
                        fails_data = json.loads(fails)
                        crit_count = sum(1 for f in fails_data if str(f.get("severity", "")).upper() == "CRITICAL" or f.get("is_critical"))
                        history[tid]["criticals"] += crit_count
                    except:
                        pass

                if usage:
                    try:
                        u = json.loads(usage)
                        for r in u.get("records", []):
                            c = r.get("cost_usd") or 0.0
                            history[tid]["avg_cost"] += c
                        history[tid]["cost_samples"] += 1
                    except:
                        pass



            query = "SELECT test_id, final_evaluation_json, usage_json, metadata_json, timestamp FROM test_sessions"
            if provider:
                query += " WHERE json_extract(metadata_json, '$.provider') = ?"
                cursor.execute(query, (provider,))
            else:
                cursor.execute(query)

            for tid, eval_json, usage, meta, ts in cursor.fetchall():
                if tid not in history:
                    history[tid] = {"runs": 0, "fails": 0, "criticals": 0, "last_ts": 0, "avg_cost": 0.0, "cost_samples": 0}

                history[tid]["runs"] += 1
                if ts > history[tid]["last_ts"]:
                    history[tid]["last_ts"] = ts

                if eval_json:
                    try:
                        ev = json.loads(eval_json)
                        if not ev.get("passed", False):
                            history[tid]["fails"] += 1
                        fails_data = ev.get("failures", [])
                        crit_count = sum(1 for f in fails_data if str(f.get("severity", "")).upper() == "CRITICAL" or f.get("is_critical"))
                        history[tid]["criticals"] += crit_count
                    except:
                        pass

                if usage:
                    try:
                        u = json.loads(usage)
                        for r in u.get("records", []):
                            c = r.get("cost_usd") or 0.0
                            history[tid]["avg_cost"] += c
                        history[tid]["cost_samples"] += 1
                    except:
                        pass

        for tid in history:
            if history[tid]["cost_samples"] > 0:
                history[tid]["avg_cost"] /= history[tid]["cost_samples"]
            else:
                history[tid]["avg_cost"] = 0.01

        return history

    def select(self, strategy: SelectionStrategy, limit: int, provider: str = None,
               seed: int = 42, max_cost: float = None, critical_max_skip_runs: int = 3) -> SelectionManifest:
        valid_tests = self.corpus_manager.get_valid_tests()

        valid_tests.sort(key=lambda t: t.test_id)

        rng = random.Random(seed)

        if strategy == SelectionStrategy.FULL:
            limit = len(valid_tests)

        history = self._fetch_history(provider)


        test_priorities = []
        import time
        now = time.time()

        for t in valid_tests:
            score = 0.0
            reasons = []
            h = history.get(t.test_id, {"runs": 0, "fails": 0, "criticals": 0, "last_ts": 0, "avg_cost": 0.01})


            skipped_runs = 0

            if strategy == SelectionStrategy.RANDOM:
                score = rng.random()
                reasons.append("random")
            elif strategy == SelectionStrategy.FAILURE_FOCUSED:
                fail_rate = (h["fails"] / h["runs"]) if h["runs"] > 0 else 0.0
                score += fail_rate * 5.0
                if h["criticals"] > 0:
                    score += 3.0
                    reasons.append("critical_history")
                if fail_rate > 0:
                    reasons.append(f"high_failure_rate ({fail_rate:.2f})")
            elif strategy == SelectionStrategy.RISK_FOCUSED:
                if t.risk_level.lower() == "high":
                    score += 5.0
                    reasons.append("high_risk_domain")
                if h["criticals"] > 0:
                    score += 5.0
                    reasons.append("critical_history")
            elif strategy == SelectionStrategy.NOVELTY_FOCUSED:
                if h["runs"] == 0:
                    score += 5.0
                    reasons.append("never_executed")
                elif now - h["last_ts"] > 86400 * 7:
                    score += 2.0
                    reasons.append("not_recently_executed")
            elif strategy == SelectionStrategy.BALANCED:
                fail_rate = (h["fails"] / h["runs"]) if h["runs"] > 0 else 0.0
                score += fail_rate * 2.0
                if h["criticals"] > 0:
                    score += 3.0
                    reasons.append("critical_history")
                if h["runs"] == 0:
                    score += 2.0
                    reasons.append("never_executed")
                if t.risk_level.lower() == "high":
                    score += 1.0
                    reasons.append("high_risk")
            elif strategy == SelectionStrategy.REGRESSION_FOCUSED:

                if h["fails"] > 0 and h["runs"] > 1:
                    score += 3.0
                    reasons.append("historical_failures")


            is_sentinel = False
            if rng.random() < 0.1 and strategy != SelectionStrategy.FULL and strategy != SelectionStrategy.RANDOM:
                score += 10.0
                reasons.append("sentinel_selection")
                is_sentinel = True



            if h["criticals"] > 0 and h["runs"] == 0:
                score += 100.0
                reasons.append("critical_starvation_prevention")

            if not reasons and strategy != SelectionStrategy.RANDOM:
                reasons.append("baseline_inclusion")

            test_priorities.append((t, score, reasons, h["avg_cost"]))


        test_priorities.sort(key=lambda x: (-x[1], x[0].test_id))


        selected = []
        accumulated_cost = 0.0

        for t, score, reasons, cost in test_priorities:
            if max_cost is not None and accumulated_cost + cost > max_cost:
                break
            selected.append(SelectedTest(
                test_id=t.test_id,
                test_version=t.test_version,
                priority_score=round(score, 3),
                reasons=reasons
            ))
            accumulated_cost += cost
            if len(selected) >= limit:
                break


        coverage_warnings = []
        selected_ids = {s.test_id for s in selected}

        selected_principles = set()
        selected_domains = set()

        for t in valid_tests:
            if t.test_id in selected_ids:
                selected_principles.update(t.principles)
                selected_domains.add(t.domain.lower())

        all_principles = {p for t in valid_tests for p in t.principles}
        all_domains = {t.domain.lower() for t in valid_tests}

        uncovered_principles = all_principles - selected_principles
        if uncovered_principles:
            coverage_warnings.append(f"0 selected tests target principles: {', '.join(uncovered_principles)}")

        uncovered_domains = all_domains - selected_domains
        if uncovered_domains:
            coverage_warnings.append(f"0 selected tests target domains: {', '.join(uncovered_domains)}")

        import uuid
        manifest = SelectionManifest(
            experiment_id=f"exp_{str(uuid.uuid4())[:8]}",
            strategy=strategy.value,
            seed=seed,
            selector_version=self.selector_version,
            selection_policy_hash=hashlib.sha256(f"{strategy.value}_{seed}".encode()).hexdigest()[:8],
            provider=provider or "any",
            selected_tests=selected,
            unselected_tests=len(valid_tests) - len(selected),
            coverage_warnings=coverage_warnings
        )

        return manifest
