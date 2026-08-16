#!/usr/bin/env python3
from pathlib import Path
import argparse
import hashlib
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()

    status = run("git", "status", "--porcelain", "--untracked-files=no")
    if status:
        raise SystemExit("Refusing to package a commit with tracked working-tree changes.")

    subprocess.run(
        ["python3", "tools/audit_public_release.py"], cwd=ROOT, check=True
    )

    commit = run("git", "rev-parse", "HEAD")
    prefix = f"behave-{commit[:8]}/"
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "git",
            "archive",
            "--format=zip",
            f"--prefix={prefix}",
            f"--output={output}",
            commit,
        ],
        cwd=ROOT,
        check=True,
    )

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum = output.with_suffix(output.suffix + ".sha256")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    print(f"Built {output}")
    print(f"SHA-256: {digest}")


if __name__ == "__main__":
    main()
