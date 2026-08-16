import os
import json
import time
import dataclasses
from typing import List, Optional, Dict, Any
from core.schema import ExperimentDefinition, DecisionPolicy, FinalDecision

REGISTRY_DIR = "registry/experiments"

class ExperimentRegistry:
    def __init__(self, registry_dir: str = REGISTRY_DIR):
        self.registry_dir = registry_dir
        if not os.path.exists(self.registry_dir):
            os.makedirs(self.registry_dir)

    def _get_path(self, experiment_id: str) -> str:
        return os.path.join(self.registry_dir, f"{experiment_id}.json")

    def create(self, definition: ExperimentDefinition) -> ExperimentDefinition:
        if not os.path.exists(self.registry_dir):
            os.makedirs(self.registry_dir, exist_ok=True)

        if not definition.created_at:
            definition.created_at = time.time()

        with open(self._get_path(definition.experiment_id), "w") as f:
            json.dump(dataclasses.asdict(definition), f, indent=2)

        return definition

    def get(self, experiment_id: str) -> Optional[ExperimentDefinition]:
        path = self._get_path(experiment_id)
        if not os.path.exists(path):
            return None

        with open(path, "r") as f:
            data = json.load(f)


        if "decision_policy" in data and isinstance(data["decision_policy"], dict):
            data["decision_policy"] = DecisionPolicy(**data["decision_policy"])

        if data.get("final_decision"):
            data["final_decision"] = FinalDecision(data["final_decision"])

        return ExperimentDefinition(**data)

    def update_status(self, experiment_id: str, status: str, final_decision: Optional[FinalDecision] = None, results_json: Optional[str] = None):
        exp = self.get(experiment_id)
        if not exp:
            raise ValueError(f"Experiment {experiment_id} not found.")

        exp.status = status
        if final_decision:
            exp.final_decision = final_decision
        if results_json:
            exp.results_json = results_json

        if status in ("COMPLETED", "FAILED") and not exp.completed_at:
            exp.completed_at = time.time()

        self.create(exp)
        return exp

    def list_all(self) -> List[ExperimentDefinition]:
        exps = []
        for f in os.listdir(self.registry_dir):
            if f.endswith(".json"):
                eid = f[:-5]
                exp = self.get(eid)
                if exp:
                    exps.append(exp)

        return sorted(exps, key=lambda x: x.created_at, reverse=True)

class DecisionEngine:

    def __init__(self, policy: DecisionPolicy):
        self.policy = policy

    def evaluate(self, stats: Dict[str, Any]) -> FinalDecision:

        score = stats.get("score_res", {})
        crit = stats.get("crit_res", {})
        res = stats.get("res_res", {})


        safety_regression = crit.get("regression", False)
        if safety_regression and not self.policy.allow_critical_regression:
            return FinalDecision.BLOCKED


        cost_inc = res.get("cost", {}).get("delta_pct", 0.0)
        lat_inc = res.get("latency", {}).get("delta_pct", 0.0)

        resource_regression = False
        if cost_inc > self.policy.max_cost_increase_pct:
            resource_regression = True
        if lat_inc > self.policy.max_latency_increase_pct:
            resource_regression = True


        behav_improved = score.get("significant", False) and score.get("delta", 0.0) > 0
        behav_regressed = score.get("significant", False) and score.get("delta", 0.0) < 0

        if self.policy.require_behavioral_improvement and not behav_improved:
            if behav_regressed:
                return FinalDecision.REGRESSION
            elif resource_regression:
                return FinalDecision.REGRESSION
            return FinalDecision.CONDITIONAL


        if behav_improved:
            if resource_regression:
                return FinalDecision.CONDITIONAL
            return FinalDecision.DEPLOY

        return FinalDecision.CONDITIONAL
