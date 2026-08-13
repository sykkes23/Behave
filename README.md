# Chimerion Evaluation Lab (MVP v0.1.0)

This is the baseline MVP for the AI Behavioral Testing & Regression Platform.

## Prerequisites
- Python 3.9+ (Built and tested with standard library only for the MVP, no external dependencies required).

## Running the MVP
The system currently tests a `MockAIModel` against deterministic behavioral JSON specifications.

1. Run the diagnostic reasoning test:
   ```bash
   python main.py tests/reasoning/diagnostic_001.json
   ```

2. Run the investment assumption test:
   ```bash
   python main.py tests/assumptions/investment_001.json
   ```

## Architecture
- `core/schema.py`: Dataclasses defining tests and evaluation results.
- `core/evaluator.py`: The evaluation engine checking for forbidden behaviors and basic logic.
- `core/test_runner.py`: Orchestrates loading the test, prompting the AI, running the evaluator, and outputting the report.
- `models/mock.py`: A simulated AI model that outputs intentional failures to prove the evaluation loop works.
- `main.py`: The CLI entry point.
