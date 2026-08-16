import subprocess
import hashlib
import json
from typing import Dict, Any, Tuple

def get_git_info() -> Tuple[str, bool]:

    try:

        commit_result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True, text=True, check=True
        )
        commit_hash = commit_result.stdout.strip()


        status_result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True, text=True, check=True
        )
        is_dirty = len(status_result.stdout.strip()) > 0

        return commit_hash, is_dirty
    except (subprocess.SubprocessError, FileNotFoundError):
        return "unknown", False

def sanitize_config(config: Dict[str, Any]) -> Dict[str, Any]:

    sanitized = config.copy()
    keys_to_redact = ["api_key", "token", "password", "secret", "GEMINI_API_KEY", "VENICE_API_KEY"]

    for k in list(sanitized.keys()):
        for redact in keys_to_redact:
            if redact.lower() in k.lower():
                sanitized[k] = "***REDACTED***"
                break
    return sanitized

def hash_dict(data: Dict[str, Any]) -> str:

    if not data:
        return "unknown"
    sanitized = sanitize_config(data)
    json_str = json.dumps(sanitized, sort_keys=True)
    return hashlib.sha256(json_str.encode('utf-8')).hexdigest()

def hash_string(text: str) -> str:

    if not text:
        return "unknown"
    return hashlib.sha256(text.encode('utf-8')).hexdigest()
