# Known Limitations

Behave is an active research prototype, not a certification system. A PASS is
evidence from the configured evaluators; it is not proof that a model is safe.

## Evaluation boundaries

- Offline deterministic rules cover a deliberately bounded set of behavior
  families and bundled criterion IDs. They are not general natural-language
  understanding.
- Negation-aware phrase matching reduces a known false-positive class but cannot
  resolve every linguistic construction.
- Behavior-family rules catch the recorded high-voltage and financial
  paraphrases, not every possible unsafe paraphrase.
- Criteria without conclusive deterministic or semantic coverage are reported
  as `INSUFFICIENT_DATA` and are not scored as PASS.
- An LLM judge can add semantic coverage but can itself be inconsistent,
  incorrect, unavailable, or vulnerable to prompt-level attacks.
- The bundled demo agents are deterministic fixtures. Their results do not
  validate performance against production models.

## Statistical and operational boundaries

- Small corpora and small sample counts can produce unstable comparisons.
- SQLite, in-memory background jobs, and the Flask development server are for
  local use, not concurrent production hosting.
- The dashboard accepts model endpoints supplied by its local user. Do not
  expose it directly to an untrusted network.
- Cost estimates depend on configured pricing metadata and provider-reported
  token usage.
- Human review remains necessary for safety-critical deployment decisions.

Reproducible counterexamples are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).
