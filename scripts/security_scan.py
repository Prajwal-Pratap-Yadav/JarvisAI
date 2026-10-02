"""Conservative repository/package gate. Never print a matched credential value."""

import re
import subprocess
import sys
import zipfile
from pathlib import Path

PATTERNS = [
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{25,}\b"),
    re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{30,}\b"),
]
BAD_PARTS = {".env", "access.token", ".ssh", "jarvis.db", "venv", ".venv", "__pycache__"}


def check(name, data):
    parts = Path(name).parts
    if any(part in BAD_PARTS for part in parts):
        return f"Prohibited artifact path: {name}"
    if any(pattern.search(data) for pattern in PATTERNS):
        return f"Potential credential in: {name}"
    return None


def main():
    root = Path(__file__).resolve().parents[1]
    if len(sys.argv) > 1:
        with zipfile.ZipFile(sys.argv[1]) as archive:
            errors = [
                error
                for name in archive.namelist()
                if not name.endswith("/") and (error := check(name, archive.read(name)))
            ]
    else:
        # Include staged new files and unstaged source, excluding deleted tracked paths.
        names = subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=root, text=True
        ).splitlines()
        errors = [
            error
            for name in names
            if (root / name).is_file() and (error := check(name, (root / name).read_bytes()))
        ]
    if errors:
        print("\n".join(errors))
        raise SystemExit(1)
    print("PASS: prohibited paths and recognized credential patterns absent")


if __name__ == "__main__":
    main()
