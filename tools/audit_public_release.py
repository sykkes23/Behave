#!/usr/bin/env python3
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]

DISALLOWED_PATHS = [
    re.compile(r"(^|/)__pycache__(/|$)"),
    re.compile(r"(^|/)\.pytest_cache(/|$)"),
    re.compile(r"(^|/)baselines(/|$)"),
    re.compile(r"^registry/experiments(/|$)"),
    re.compile(r"\.(?:pyc|db|log|tar\.gz)$"),
]

SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "GitHub token": re.compile(r"(?:github_pat_|gh[pousr]_)[A-Za-z0-9_]{20,}"),
    "OpenAI-style key": re.compile(r"\bsk-[A-Za-z0-9_-]{32,}\b"),
    "Google API key": re.compile(r"\bAIza[A-Za-z0-9_-]{30,}\b"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "local home path": re.compile(r"/(?:home|Users)/[^/\s]+/"),
}


def tracked_files() -> list[str]:
    inside_git = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=ROOT,
        capture_output=True,
    )
    if inside_git.returncode != 0:
        return sorted(
            str(path.relative_to(ROOT))
            for path in ROOT.rglob("*")
            if path.is_file()
        )

    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [item.decode() for item in result.stdout.split(b"\0") if item]


def main() -> int:
    findings: list[str] = []
    files = tracked_files()

    for relative in files:
        if any(pattern.search(relative) for pattern in DISALLOWED_PATHS):
            findings.append(f"disallowed tracked artifact: {relative}")
            continue

        path = ROOT / relative
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                findings.append(f"possible {label}: {relative}")

    if findings:
        print("Public-release audit failed:")
        for finding in sorted(set(findings)):
            print(f"- {finding}")
        return 1

    print(f"Public-release audit passed ({len(files)} tracked files checked).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
