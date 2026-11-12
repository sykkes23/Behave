# Behave — find the bugs your AI doesn't tell you about

Changing a prompt or switching models is easy. Knowing whether the change actually made things better? That's the hard part.

I built **Behave** to answer that question with tests instead of guesses. It runs repeatable conversations against a baseline and a candidate AI, checks what changed, and gives you the evidence to decide whether the new version is worth keeping.

It's an engineering tool, not another chatbot.

## What it does

- **Compares versions:** Run the same scenarios against a baseline and a changed model or prompt.
- **Catches regressions:** Look for behavioral failures, including safety problems that can get buried in average scores.
- **Tests conversations, not just single replies:** Follow behavior across multiple turns.
- **Tracks the trade-offs:** Compare scores alongside latency, token use, and estimated cost when the provider supplies the needed data.
- **Keeps humans in the loop:** Review automated judgments and record overrides.
- **Doesn't fake a pass:** If a test can't be evaluated reliably, Behave reports `INSUFFICIENT_DATA` instead of quietly handing out a perfect score.

The point is simple: **if an AI changes, I want to know exactly what got better, what got worse, and why.**

## Try it without an API key

There's a built-in demo with two simulated versions of an AI. It's a quick way to see the testing flow without configuring a provider.

**Windows:** Double-click `Start_Behave.bat`.

**macOS / Linux:**

```bash
./Start_Behave.sh
```

The launcher sets up the local Python environment on first run. Open `http://127.0.0.1:5000` if the dashboard doesn't open automatically.

In the dashboard:

1. Choose **TRY DEMO**.
2. Select **Demo Agent (Built-in)**.
3. Run the sample comparison and inspect the results.

The demo uses deterministic test agents. It's a walkthrough of the evaluation pipeline, **not** a claim that a production model has been validated.

## Test your own endpoint

Use **TEST MY AI** in the dashboard and configure the baseline and candidate endpoints. For example, a local Ollama endpoint can be used if you've already got Ollama running.

The evaluation interface supports smaller quick runs and larger test sets, depending on the scenarios you configure. Endpoint compatibility, usage reporting, and evaluator coverage depend on the provider and setup.

## Under the hood

- **Python + Flask** for the local dashboard and evaluation API
- **SQLite** for local test results
- A repeatable **test corpus**, baseline comparisons, and experiment tracking
- **Stateful evaluation**, failure categories, decision rules, and human review
- A provider interface so the testing logic isn't tied to one model

I deliberately kept it local-first and relatively lightweight. I'd rather have a tool that's understandable and testable than a giant stack that makes a simple problem harder.

## Run checks

```bash
python -m pytest -q
python tools/audit_public_release.py
```

These are the project's test and public-release audit commands. Run them before sharing a new build or source archive.

## What it is — and isn't

Behave is an **active research prototype**. It can surface measurable regressions using configured tests and evaluators; it **cannot certify an AI as safe or guarantee a result**. Small test sets can be misleading, automated judges make mistakes, and production deployments need more infrastructure and human review.

The dashboard runs locally. If you connect it to a remote AI provider, requests to that endpoint are handled under that provider's rules.

For the actual boundaries, see [Known Limitations](KNOWN_LIMITATIONS.md). Security issues go through [SECURITY.md](SECURITY.md), and reproducible bug reports are covered in [CONTRIBUTING.md](CONTRIBUTING.md).

## License

The code is **source-available for inspection, testing, and research review**, not open-source licensed for unrestricted reuse. See [LICENSE](LICENSE).
