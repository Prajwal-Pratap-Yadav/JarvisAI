"""Persistent, at-most-once reminder dispatch. No silent scheduled side effects."""

import asyncio
import json
import time
import uuid
from typing import Literal

import psutil
from pydantic import BaseModel, Field

from jarvis.events import EventBus
from jarvis.security import PathPolicy
from jarvis.storage import Store


class ScheduleInput(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    due: float = Field(gt=0)
    interval: int | None = Field(default=None, ge=60, le=31536000)
    kind: Literal["reminder", "file_watch", "process_watch"] = "reminder"
    path: str = ""
    pid: int | None = Field(default=None, gt=0)


class Scheduler:
    def __init__(self, store: Store, bus: EventBus, paths: PathPolicy):
        self.store, self.bus, self.paths = store, bus, paths

    def list(self) -> list[dict]:
        return [
            json.loads(r[0])
            for r in self.store.db.execute("SELECT body FROM schedules ORDER BY due")
        ]

    def add(self, item: ScheduleInput) -> dict:
        if len(self.list()) >= 100:
            raise ValueError("Schedule limit reached (100)")
        record = {**item.model_dump(), "id": uuid.uuid4().hex, "enabled": True}
        if item.kind == "file_watch":
            path = self.paths.resolve(item.path)
            record["last_mtime"] = path.stat().st_mtime_ns if path.exists() else None
        if item.kind == "process_watch":
            if not item.pid:
                raise ValueError("Process watches require a PID")
            try:
                record["process_created"] = psutil.Process(item.pid).create_time()
            except psutil.NoSuchProcess as exc:
                raise ValueError("The selected process does not exist") from exc
        self.save(record)
        return record

    def save(self, record: dict) -> None:
        with self.store.db:
            self.store.db.execute(
                "INSERT OR REPLACE INTO schedules VALUES(?,?,?)",
                (record["id"], record["due"], json.dumps(record)),
            )

    def delete(self, ident: str) -> bool:
        with self.store.db:
            return bool(
                self.store.db.execute("DELETE FROM schedules WHERE id=?", (ident,)).rowcount
            )

    async def tick(self, now: float | None = None) -> None:
        now = time.time() if now is None else now
        for record in self.list():
            if not record["enabled"] or record["due"] > now:
                continue
            notify = True
            if record["kind"] == "file_watch":
                try:
                    path = self.paths.resolve(record["path"])
                    mtime = path.stat().st_mtime_ns if path.exists() else None
                    notify = mtime != record.get("last_mtime")
                    record["last_mtime"] = mtime
                except (OSError, ValueError):
                    record["enabled"] = False
                    notify = False
            if record["kind"] == "process_watch":
                try:
                    notify = (
                        psutil.Process(record["pid"]).create_time() != record["process_created"]
                    )
                except psutil.NoSuchProcess:
                    notify = True
                if notify:
                    record["enabled"] = False
            if record["interval"] or record["kind"] != "reminder":
                record["due"] = now + (record["interval"] or 60)
            else:
                record["enabled"] = False
            # Advance before dispatch: restart does not replay old notifications in a burst.
            self.save(record)
            if notify:
                await self.bus.publish(
                    "SYSTEM_ALERT",
                    {"schedule_id": record["id"], "title": record["title"], "kind": record["kind"]},
                )

    async def loop(self) -> None:
        while True:
            await self.tick()
            await asyncio.sleep(1)
