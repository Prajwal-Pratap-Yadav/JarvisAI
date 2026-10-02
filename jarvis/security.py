"""Central policy: confined paths, bounded secrets, and exact-action confirmations."""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class Denied(ValueError):
    """An operation is outside the configured trust boundary."""


class Unavailable(RuntimeError):
    """An optional capability is not configured or not installed."""


_SECRET = re.compile(
    r"(?i)(?:\b(?:sk-[a-z0-9_-]{16,}|gh[pousr]_[a-z0-9]{20,})\b|"
    r"(?:api[_-]?key|password|secret|token)\s*[:=]\s*[^\s,;]+|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return _SECRET.sub("[REDACTED]", value)
    if isinstance(value, dict):
        return {
            k: "[REDACTED]" if re.search(r"(?i)password|secret|token|api.?key", k) else redact(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def contains_secret(text: str) -> bool:
    return bool(_SECRET.search(text))


class PathPolicy:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def resolve(self, name: str, *, write: bool = False) -> Path:
        if not name or "\x00" in name or ":" in name:
            raise Denied("A workspace-relative path is required")
        raw = Path(name.replace("\\", "/"))
        if raw.is_absolute() or ".." in raw.parts:
            raise Denied("Paths must stay inside the workspace")
        current = self.root
        for part in raw.parts:
            current = current / part
            if current.is_symlink():
                raise Denied("Symlink paths are not permitted")
            # Block git internals and credential files for both read and write tools.
            if part in {
                ".git",
                ".ssh",
                ".aws",
                ".azure",
                ".env",
                "access.token",
            } or part.startswith(".env."):
                raise Denied("Credential and repository metadata paths are protected")
        resolved = current.resolve()
        if not resolved.is_relative_to(self.root):
            raise Denied("Path escapes the workspace")
        if write and resolved == self.root:
            raise Denied("Cannot replace the workspace directory")
        return resolved


@dataclass
class Approval:
    id: str
    run_id: str
    node_id: str
    tool: str
    digest: str
    arguments: dict[str, Any]
    expires: float

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "node_id": self.node_id,
            "tool": self.tool,
            "arguments": redact(self.arguments),
            "expires": self.expires,
        }


class ApprovalGate:
    """Approvals never come from model output and never grant blanket permission."""

    def __init__(self) -> None:
        self.pending: dict[str, Approval] = {}
        self.grants: dict[tuple[str, str], str] = {}

    @staticmethod
    def digest(tool: str, arguments: dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps([tool, arguments], sort_keys=True).encode()).hexdigest()

    def request(self, run_id: str, node_id: str, tool: str, arguments: dict[str, Any]) -> Approval:
        self.prune()
        digest = self.digest(tool, arguments)
        for approval in self.pending.values():
            if (approval.run_id, approval.node_id, approval.digest) == (run_id, node_id, digest):
                return approval
        approval = Approval(
            secrets.token_hex(12), run_id, node_id, tool, digest, arguments, time.time() + 600
        )
        self.pending[approval.id] = approval
        return approval

    def decide(self, approval_id: str, allowed: bool) -> Approval:
        self.prune()
        approval = self.pending.pop(approval_id, None)
        if not approval:
            raise Denied("Approval is missing, consumed, or expired")
        if allowed:
            self.grants[(approval.run_id, approval.node_id)] = approval.digest
        return approval

    def consume(self, run_id: str, node_id: str, tool: str, arguments: dict[str, Any]) -> bool:
        granted = self.grants.pop((run_id, node_id), None)
        return granted == self.digest(tool, arguments)

    def clear_run(self, run_id: str) -> None:
        self.pending = {k: a for k, a in self.pending.items() if a.run_id != run_id}
        self.grants = {k: d for k, d in self.grants.items() if k[0] != run_id}

    def prune(self) -> None:
        self.pending = {k: a for k, a in self.pending.items() if a.expires > time.time()}
