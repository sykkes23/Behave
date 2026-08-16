# Contributing to Behave

Behave welcomes reproducible behavioral failures, adversarial test cases, and
small, evidence-backed fixes.

## Useful bug reports

Include:

- the Behave commit hash;
- the exact test ID and model response;
- the reported verdict and score;
- the expected verdict and why;
- whether the result reproduces consistently; and
- sanitized logs, if needed.

Do not include credentials, private endpoints, personal data, or production
conversation content.

## Development workflow

1. Make the smallest change that resolves one measured problem.
2. Add a regression test before or with the fix.
3. Run `python -m pytest -q`.
4. Run `python tools/audit_public_release.py`.
5. Update the relevant documentation.

Evaluation criteria without deterministic or semantic coverage must return an
explicit uncertain/not-evaluated result. They must never silently pass.
