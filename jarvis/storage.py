"""SQLite persistence with WAL, atomic checkpoints, and bounded history retention."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from jarvis.security import redact


class Store:
    def __init__(self, path: Path):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, updated REAL, body TEXT);
        CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, run_id TEXT, kind TEXT, body TEXT);
        CREATE INDEX IF NOT EXISTS events_run ON events(run_id, seq);
        CREATE TABLE IF NOT EXISTS memories(id TEXT PRIMARY KEY, kind TEXT, content TEXT, source TEXT, confidence REAL, updated REAL, metadata TEXT, fingerprint TEXT UNIQUE);
        CREATE TABLE IF NOT EXISTS schedules(id TEXT PRIMARY KEY, due REAL, body TEXT);
        PRAGMA user_version=1;
        """)
        self.db.commit()
        path.chmod(0o600)

    def save_run(self, run: dict[str, Any]) -> None:
        with self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO runs VALUES(?,?,?)",
                (run["id"], time.time(), json.dumps(redact(run))),
            )

    def runs(self, limit: int = 100) -> list[dict[str, Any]]:
        return [
            json.loads(r[0])
            for r in self.db.execute(
                "SELECT body FROM runs ORDER BY updated DESC LIMIT ?", (limit,)
            )
        ]

    def run(self, run_id: str) -> dict[str, Any] | None:
        row = self.db.execute("SELECT body FROM runs WHERE id=?", (run_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def add_event(self, kind: str, data: dict[str, Any], run_id: str | None) -> dict[str, Any]:
        ts = time.time()
        data = redact(data)
        with self.db:
            cursor = self.db.execute(
                "INSERT INTO events(ts,run_id,kind,body) VALUES(?,?,?,?)",
                (ts, run_id, kind, json.dumps(data)),
            )
        return {"seq": cursor.lastrowid, "ts": ts, "run_id": run_id, "kind": kind, "data": data}

    def events(
        self, after: int = 0, run_id: str | None = None, limit: int = 500
    ) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT * FROM events WHERE seq>? AND (? IS NULL OR run_id=?) ORDER BY seq LIMIT ?",
            (after, run_id, run_id, limit),
        )
        return [
            {
                "seq": r["seq"],
                "ts": r["ts"],
                "run_id": r["run_id"],
                "kind": r["kind"],
                "data": json.loads(r["body"]),
            }
            for r in rows
        ]

    def prune(self, days: int) -> None:
        before = time.time() - days * 86400
        with self.db:
            self.db.execute("DELETE FROM events WHERE ts<?", (before,))
            self.db.execute("DELETE FROM runs WHERE updated<?", (before,))

    def close(self) -> None:
        self.db.close()
