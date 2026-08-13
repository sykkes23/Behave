# AI Evaluation Lab — Post-MVP Engineering Specification

## Context
You have already built **v0.1 MVP** consisting of the core evaluation loop:
> **Test → AI Response → Evaluation → SQLite → Dashboard/Results**

The MVP was intentionally kept small.

Your previous architectural critique identified four major issues:
1. LLM-as-judge can incorrectly reject valid reasoning.
2. Failure categories are ambiguous.
3. Stateless tests cannot measure behavioral change over multiple turns.
4. Average scores can hide critical failures.

We agree with those findings.
We also want the system to support **multiple AI providers**, initially:
* **Google Gemini API**
* **Venice API**
* local models later

The system must therefore become a **model/provider-agnostic AI evaluation laboratory**, while remaining primarily a tool for developing and testing Chimerion during the early phases.

## PRIMARY OBJECTIVE
Do **not** turn this into a giant AI platform.
> **Create a reliable, reproducible system capable of detecting, recording, comparing, and learning from behavioral failures in AI systems.**

## NON-NEGOTIABLE DEVELOPMENT RULE
Work **one phase at a time**.
For each phase:
1. Inspect the existing implementation.
2. Make the smallest necessary changes.
3. Run the existing tests.
4. Add tests for the new functionality.
5. Demonstrate that the phase works.
6. Update documentation.
7. Commit the changes.
8. **STOP.**

## PHASE 0 — FREEZE THE CURRENT MVP
Before modifying functionality:
* Commit current code.
* Tag it: `v0.1.0`
* Back up SQLite database.
* Preserve current test results.
* Record current dependency versions.
* Record current configuration.
* Document how to reproduce the current MVP.

## PHASE 1 — HUMAN EVALUATION OVERRIDE
The evaluator is **not infallible**.
Every automatic evaluation must support human review.

## PHASE 2 — FAILURE TAXONOMY
Replace simplistic single-category failure classification with structured multi-tagging.

## PHASE 3 — VERSION / REPRODUCIBILITY SYSTEM
Every evaluation needs enough metadata to reproduce it.

## PHASE 4 — PROVIDER ABSTRACTION
Create a provider interface. Do not hard-code evaluation logic to Gemini or Venice.

## PHASE 5 — GEMINI + VENICE
Implement the first two providers using API keys from environment variables.

## PHASE 6 — COST + PERFORMANCE TRACKING
Every inference must record tokens, cost, latency, and retries.

## PHASE 7 — CRITICAL FAILURE GATES
Do not allow dangerous failures to disappear inside averages.

## PHASE 8 — EVALUATION EVIDENCE MODEL
An evaluator must produce structured evidence, not merely PASS/FAIL.

## PHASE 9 — EVALUATOR DISAGREEMENT
Track agreement/disagreement across evaluation layers.

## PHASE 10 — STATEFUL TEST ENGINE
Tests must eventually support events and preserve session state.

## PHASE 11 — TRAJECTORY EVALUATION
Evaluate behavioral change across the entire session.

## PHASE 12 — REGRESSION SUITE
Every confirmed behavioral failure becomes a permanent regression test.

## PHASE 13 — BEHAVIORAL METRICS
Track behavioral dimensions independently. Show trends over time.

## PHASE 14 — CONTROLLED TEST GENERATION
Only after the evaluation system is reliable. Impose hard limits.

## PHASE 15 — MODEL COMPARISON
Compare behavior across multiple models/providers.

## PHASE 16 — COST-AWARE ROUTING
Intelligent routing based on test complexity and cost.

## PHASE 17 — EXPERIMENT LOOP
Hypothesis -> generate test -> run -> evaluate -> keep/reject.

## PHASE 18 — GENERALIZATION DECISION
Decide if this becomes a general framework, product, or just a dev tool.

## HARD CONSTRAINTS
DO: local-first, SQLite, reproducible tests, Git versioning, provider abstraction, Gemini/Venice support, cost tracking, human override, evidence-based evaluation, critical-failure gates, incremental development.
DO NOT: Kubernetes, microservices, SaaS platform, unnecessary cloud infra, assume unlimited API, unquestionable LLM judges, exponential test generation, average away critical failures, autonomous code mod, rewrite without necessity.
