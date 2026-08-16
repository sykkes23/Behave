# Security Policy

Behave evaluates untrusted model output and can connect to user-supplied model
endpoints. Run it only on a machine and network you control. The Flask dashboard
is a local development service; it is not hardened for direct internet exposure.

## Reporting a vulnerability

Please report suspected vulnerabilities privately through GitHub's **Security**
tab rather than opening a public issue. Include the affected commit, a minimal
reproduction, impact, and any logs with credentials removed.

Never include API keys, access tokens, private endpoints, database contents, or
other personal data in an issue, pull request, test fixture, or release archive.

## Credential handling

- Supply provider credentials at runtime; never commit them.
- Use environment variables or the local dashboard form only on a trusted host.
- Revoke any credential that was pasted into chat, a terminal command, or a log.
- Run `python tools/audit_public_release.py` before publishing source.

Generated databases, logs, experiment registries, baselines, caches, and release
archives are intentionally excluded from version control.
