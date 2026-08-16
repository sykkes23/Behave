import os
import json
import uuid
import dataclasses
import threading
import time
import traceback
from flask import Flask, jsonify, request, render_template, send_file
import io

from core.experiment_registry import ExperimentRegistry, DecisionEngine
from core.schema import ExperimentDefinition, DecisionPolicy
from core.corpus import CorpusManager
from core.reliability import MeasurementIntegrity
from statistics import load_baseline
from core.statistics import ExperimentAnalytics
from core.evaluator import Evaluator
from core.test_runner import TestRunner
from models.factory import get_provider
from models.provider import ProviderConfig
from database.sqlite import save_test_result, init_db
from core.baseline import create_baseline
from core.judge import LLMJudge

app = Flask(__name__)
reg = ExperimentRegistry()
corpus_manager = CorpusManager("tests")
mi = MeasurementIntegrity()


init_db()


jobs = {}


def asdict_safe(obj):
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/experiments", methods=["GET"])
def list_experiments():
    exps = reg.list_all()

    data = []
    for exp in exps:
        d = asdict_safe(exp)
        if exp.final_decision:
            d["final_decision"] = exp.final_decision.value
        data.append(d)
    return jsonify(data)

@app.route("/api/experiments", methods=["POST"])
def create_experiment():
    req = request.json
    exp_id = f"exp_{uuid.uuid4().hex[:8]}"
    pol = DecisionPolicy(
        max_cost_increase_pct=req.get("max_cost_inc", 20.0),
        max_latency_increase_pct=req.get("max_lat_inc", 10.0)
    )
    exp = ExperimentDefinition(
        experiment_id=exp_id,
        hypothesis=req.get("hypothesis", ""),
        baseline=req.get("baseline", ""),
        candidate=req.get("candidate", ""),
        budget=req.get("budget", 10.0),
        decision_policy=pol
    )
    reg.create(exp)
    return jsonify(asdict_safe(exp)), 201

@app.route("/api/experiments/<exp_id>", methods=["GET"])
def get_experiment(exp_id):
    exp = reg.get(exp_id)
    if not exp:
        return jsonify({"error": "Not found"}), 404
    d = asdict_safe(exp)
    if exp.final_decision:
        d["final_decision"] = exp.final_decision.value
    return jsonify(d)

@app.route("/api/experiments/<exp_id>/run", methods=["POST"])
def run_experiment(exp_id):
    exp = reg.get(exp_id)
    if not exp:
        return jsonify({"error": "Not found"}), 404


    reg.update_status(exp_id, "RUNNING")

    b_runs = load_baseline(exp.baseline)
    c_runs = load_baseline(exp.candidate)

    if not b_runs or not c_runs:
        reg.update_status(exp_id, "FAILED")
        return jsonify({"error": "Runs missing"}), 400

    analytics = ExperimentAnalytics(b_runs, c_runs)
    stats = {
        "score_res": analytics.analyze_scores(),
        "crit_res": analytics.analyze_criticals(),
        "res_res": analytics.analyze_resources(),
        "tag_res": analytics.analyze_tags()
    }

    engine = DecisionEngine(exp.decision_policy)
    decision = engine.evaluate(stats)

    exp = reg.update_status(exp_id, "COMPLETED", decision, json.dumps(stats))
    d = asdict_safe(exp)
    d["final_decision"] = exp.final_decision.value
    return jsonify(d)

@app.route("/api/experiments/<exp_id>/results", methods=["GET"])
def get_experiment_results(exp_id):
    exp = reg.get(exp_id)
    if not exp or not exp.results_json:
        return jsonify({"error": "No results found"}), 404

    return jsonify(json.loads(exp.results_json))

@app.route("/api/tests", methods=["GET"])
def list_tests():
    tests = corpus_manager.get_valid_tests()
    return jsonify([asdict_safe(t) for t in tests])

@app.route("/api/tests/<test_id>", methods=["GET"])
def get_test(test_id):
    if test_id not in corpus_manager.tests:
        return jsonify({"error": "Not found"}), 404
    return jsonify(asdict_safe(corpus_manager.tests[test_id]))

@app.route("/api/baselines", methods=["GET"])
def list_baselines():
    base_dir = "baselines"
    if not os.path.exists(base_dir):
        return jsonify([])
    return jsonify(os.listdir(base_dir))

@app.route("/api/baselines/<base_id>", methods=["GET"])
def get_baseline(base_id):
    runs = load_baseline(base_id)
    if not runs:
        return jsonify({"error": "Not found"}), 404
    return jsonify(runs)

@app.route("/api/reliability", methods=["GET"])
def get_reliability():
    report = mi.generate_report()
    return jsonify(report)

def run_evaluation_job(job_id, exp_id, tests, v1_config, v2_config, is_demo=False):
    try:
        if is_demo:

            judge_config = ProviderConfig(provider_name="mock", model_name="judge")
            valid_json = '{"verdict": "PASS", "criteria_results": [{"criterion_id": "c1", "verdict": "PASS", "evidence": "Looks good"}], "failures": []}'
            judge_provider = get_provider(judge_config, mock_responses={"default": valid_json})
            evaluator = Evaluator(None)
        else:

            evaluator = Evaluator(None)

        total_tests = len(tests)


        runner_v1 = TestRunner(get_provider(v1_config), evaluator)
        for i, test in enumerate(tests):
            res = runner_v1.run_test(test)
            save_test_result(res)
            jobs[job_id]["progress"] = int(((i + 1) / (total_tests * 2)) * 100)
            jobs[job_id]["message"] = f"Running baseline tests ({i+1}/{total_tests})..."

        create_baseline("agent_v1_demo", provider=v1_config.provider_name)


        runner_v2 = TestRunner(get_provider(v2_config), evaluator)
        for i, test in enumerate(tests):
            res = runner_v2.run_test(test)
            save_test_result(res)
            jobs[job_id]["progress"] = int(((total_tests + i + 1) / (total_tests * 2)) * 100)
            jobs[job_id]["message"] = f"Running candidate tests ({i+1}/{total_tests})..."

        create_baseline("agent_v2_demo", provider=v2_config.provider_name)


        jobs[job_id]["message"] = "Calculating statistics and decision..."
        b_runs = load_baseline("agent_v1_demo")
        c_runs = load_baseline("agent_v2_demo")

        analytics = ExperimentAnalytics(b_runs, c_runs)
        stats = {
            "score_res": analytics.analyze_scores(),
            "crit_res": analytics.analyze_criticals(),
            "res_res": analytics.analyze_resources(),
            "tag_res": analytics.analyze_tags()
        }

        exp = reg.get(exp_id)
        engine = DecisionEngine(exp.decision_policy)
        decision = engine.evaluate(stats)

        reg.update_status(exp_id, "COMPLETED", decision, json.dumps(stats))

        jobs[job_id]["progress"] = 100
        jobs[job_id]["status"] = "COMPLETED"
        jobs[job_id]["message"] = "Evaluation complete."
        jobs[job_id]["experiment_id"] = exp_id

    except Exception as e:
        traceback.print_exc()
        jobs[job_id]["status"] = "FAILED"
        jobs[job_id]["error"] = (
            "The evaluation could not complete. Check that both AI endpoints "
            "are reachable and correctly configured."
        )

@app.route("/api/demo/start", methods=["POST"])
def start_demo():
    job_id = uuid.uuid4().hex
    exp_id = f"exp_demo_{job_id[:8]}"

    pol = DecisionPolicy(max_cost_increase_pct=20.0, allow_critical_regression=False)
    exp = ExperimentDefinition(
        experiment_id=exp_id,
        hypothesis="Agent v2 safely improves diagnostics and risk calibration.",
        baseline="agent_v1_demo",
        candidate="agent_v2_demo",
        decision_policy=pol
    )
    reg.create(exp)

    tests = corpus_manager.get_valid_tests()

    v1_config = ProviderConfig(provider_name="http", api_base="http://localhost:8080/v1/chat")
    v2_config = ProviderConfig(provider_name="http", api_base="http://localhost:8080/v2/chat")

    jobs[job_id] = {"status": "RUNNING", "progress": 0, "message": "Starting demo...", "experiment_id": exp_id}

    thread = threading.Thread(target=run_evaluation_job, args=(job_id, exp_id, tests, v1_config, v2_config, True))
    thread.start()

    return jsonify({"job_id": job_id})

@app.route("/api/test_ai/start", methods=["POST"])
def start_test_ai():
    req = request.json
    job_id = uuid.uuid4().hex
    exp_id = f"exp_test_{job_id[:8]}"

    v1_endpoint = req.get("baseline_endpoint")
    v2_endpoint = req.get("candidate_endpoint")
    provider_type = req.get("provider", "http")
    test_size = req.get("size", "QUICK")
    api_key = req.get("api_key", "")

    pol = DecisionPolicy(max_cost_increase_pct=20.0, allow_critical_regression=False)
    exp = ExperimentDefinition(
        experiment_id=exp_id,
        hypothesis="Candidate agent outperforms baseline on chosen corpus.",
        baseline="agent_v1_demo",
        candidate="agent_v2_demo",
        decision_policy=pol
    )
    reg.create(exp)

    all_tests = corpus_manager.get_valid_tests()
    if test_size == "QUICK":
        tests = all_tests[:10]
    elif test_size == "STANDARD":
        tests = all_tests[:50]
    else:
        tests = all_tests

    if not v1_endpoint or not v2_endpoint:
        return jsonify({"error": "Missing endpoints"}), 400

    v1_config = ProviderConfig(provider_name=provider_type, api_base=v1_endpoint, api_key=api_key)
    v2_config = ProviderConfig(provider_name=provider_type, api_base=v2_endpoint, api_key=api_key)

    jobs[job_id] = {"status": "RUNNING", "progress": 0, "message": "Starting evaluation...", "experiment_id": exp_id}

    thread = threading.Thread(target=run_evaluation_job, args=(job_id, exp_id, tests, v1_config, v2_config, False))
    thread.start()

    return jsonify({"job_id": job_id})

@app.route("/api/jobs/<job_id>", methods=["GET"])
def get_job_status(job_id):
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(jobs[job_id])

@app.route("/api/report/<exp_id>/json", methods=["GET"])
def export_report_json(exp_id):
    exp = reg.get(exp_id)
    if not exp or not exp.results_json:
        return jsonify({"error": "No results found"}), 404

    report = {
        "experiment_id": exp.experiment_id,
        "baseline": exp.baseline,
        "candidate": exp.candidate,
        "decision": exp.final_decision.value if exp.final_decision else "UNKNOWN",
        "results": json.loads(exp.results_json)
    }

    mem = io.BytesIO()
    mem.write(json.dumps(report, indent=2).encode('utf-8'))
    mem.seek(0)

    return send_file(
        mem,
        mimetype="application/json",
        as_attachment=True,
        download_name=f"behave_report_{exp_id}.json"
    )

if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5000)
