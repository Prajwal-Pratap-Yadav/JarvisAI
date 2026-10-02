"""User-controlled memory with provenance and explicit, conservative consolidation."""

from __future__ import annotations

import builtins
import hashlib
import json
import math
import re
import time
import uuid
from collections import Counter
from typing import Any, Literal

from pydantic import BaseModel, Field

from jarvis.security import Denied, contains_secret
from jarvis.storage import Store

MemoryKind = Literal["working", "episodic", "semantic", "procedural", "task", "preference"]


class MemoryInput(BaseModel):
    kind: MemoryKind = "semantic"
    content: str = Field(min_length=1, max_length=16000)
    source: str = Field(default="user", max_length=200)
    confidence: float = Field(default=1, ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


def vector(text: str) -> Counter:
    return Counter(re.findall(r"\w+", text.lower()))


def similarity(a: Counter, b: Counter) -> float:
    denominator = math.sqrt(sum(v * v for v in a.values()) * sum(v * v for v in b.values()))
    return sum(v * b[k] for k, v in a.items()) / denominator if denominator else 0


class Memory:
    def __init__(self, store: Store):
        self.store = store
        self.working: dict[str, list[dict[str, str]]] = {}

    def context(self, session: str, role: str, content: str) -> list[dict[str, str]]:
        if session not in self.working and len(self.working) >= 100:
            self.working.pop(next(iter(self.working)))
        items = self.working.setdefault(session, [])
        items.append({"role": role, "content": content[:16000]})
        del items[:-12]
        return list(items)

    def put(
        self, item: MemoryInput, *, approved: bool = False, memory_id: str | None = None
    ) -> dict:
        if not approved:
            raise Denied("Long-term memory requires explicit user approval")
        if item.kind == "working":
            raise Denied("Working context is deliberately ephemeral")
        if contains_secret(item.content) or contains_secret(json.dumps(item.metadata)):
            raise Denied("Potential credentials must not be stored as memory")
        fingerprint = hashlib.sha256(
            f"{item.kind}:{' '.join(item.content.lower().split())}".encode()
        ).hexdigest()
        existing = self.store.db.execute(
            "SELECT id FROM memories WHERE fingerprint=?", (fingerprint,)
        ).fetchone()
        if existing and memory_id and existing[0] != memory_id:
            raise Denied("This memory already exists")
        ident = memory_id or (existing[0] if existing else uuid.uuid4().hex)
        with self.store.db:
            self.store.db.execute(
                "INSERT OR REPLACE INTO memories VALUES(?,?,?,?,?,?,?,?)",
                (
                    ident,
                    item.kind,
                    item.content,
                    item.source,
                    item.confidence,
                    time.time(),
                    json.dumps(item.metadata),
                    fingerprint,
                ),
            )
        return next(m for m in self.list() if m["id"] == ident)

    def list(self) -> list[dict]:
        rows = self.store.db.execute("SELECT * FROM memories ORDER BY updated DESC LIMIT 5000")
        return [{**dict(r), "metadata": json.loads(r["metadata"])} for r in rows]

    def search(self, query: str, limit: int = 8) -> builtins.list[dict]:
        query_vector = vector(query)
        candidates = [
            {**r, "relevance": round(similarity(query_vector, vector(r["content"])), 4)}
            for r in self.list()
        ]
        return sorted(
            (r for r in candidates if r["relevance"] > 0),
            key=lambda r: r["relevance"],
            reverse=True,
        )[:limit]

    def delete(self, memory_id: str) -> bool:
        with self.store.db:
            return bool(
                self.store.db.execute("DELETE FROM memories WHERE id=?", (memory_id,)).rowcount
            )

    def candidate(self, content: str, source: str, importance: float) -> dict | None:
        """Produce a reviewable candidate; never silently persist interactions."""
        if importance < 0.7 or contains_secret(content) or len(content.strip()) < 8:
            return None
        if any(r["relevance"] > 0.95 for r in self.search(content)):
            return None
        return MemoryInput(content=content, source=source, confidence=importance).model_dump()
