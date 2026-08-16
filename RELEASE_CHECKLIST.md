# Public Release Checklist

Before changing repository visibility or distributing a source archive:

1. Confirm the intended commit and that the working tree contains no unrelated
   changes.
2. Run `python -m pytest -q`.
3. Run `python tools/audit_public_release.py`.
4. Confirm no database, log, cache, generated baseline, experiment record,
   credential file, or archive is tracked.
5. Scan the complete Git history, branches, and tags for credentials and local
   runtime state. Removing a file in the latest commit does not remove history.
6. Build distributions only from the audited Git tree, never with a broad copy
   of the development directory. Use
   `python tools/build_public_distribution.py --output behave-public.zip`.
7. Extract the distribution into a new temporary directory. Run the
   public-release audit there first, then rerun the tests.
8. Review `KNOWN_LIMITATIONS.md`, `SECURITY.md`, and the license for accuracy.
9. Keep the GitHub repository private until the cleaned history is pushed and
   independently rechecked.

If a real credential appears anywhere in history, revoke it before publication
and rewrite the affected Git references.
