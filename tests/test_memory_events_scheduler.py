import pytest

from jarvis.memory import MemoryInput
from jarvis.scheduler import ScheduleInput, Scheduler
from jarvis.security import Denied


async def test_memory_consent_dedup_update_delete(runtime):
    memory = runtime.memory
    item = MemoryInput(content="Prefer Python for backend tools", kind="preference")
    with pytest.raises(Denied):
        memory.put(item)
    first = memory.put(item, approved=True)
    again = memory.put(item, approved=True)
    assert first["id"] == again["id"] and len(memory.list()) == 1
    assert memory.search("Python backend")[0]["id"] == first["id"]
    memory.put(MemoryInput(content="Prefer Rust"), approved=True, memory_id=first["id"])
    assert memory.search("Rust")
    assert memory.delete(first["id"]) and not memory.list()


async def test_sensitive_memory_rejected_and_candidates_not_persisted(runtime):
    with pytest.raises(Denied):
        runtime.memory.put(MemoryInput(content="password=hunter2"), approved=True)
    assert runtime.memory.candidate("Use tests before writing a patch", "run:1", 0.8)
    assert not runtime.memory.list()
    assert runtime.memory.candidate("trivial", "run:1", 0.2) is None


async def test_bounded_ephemeral_context(runtime):
    for i in range(30):
        runtime.memory.context("s", "user", str(i))
    assert len(runtime.memory.working["s"]) == 12


async def test_event_redaction_and_slow_subscriber(runtime):
    async with runtime.bus.subscribe() as queue:
        for i in range(300):
            await runtime.bus.publish("TEST", {"number": i, "api_key": "secret"})
        assert queue.qsize() == 256
        assert (await queue.get())["data"]["number"] == 44
    assert not runtime.bus.subscribers
    assert runtime.store.events()[-1]["data"]["api_key"] == "[REDACTED]"


async def test_scheduler_restart_and_no_catchup_storm(runtime):
    scheduler = runtime.scheduler
    record = scheduler.add(ScheduleInput(title="Review status", due=100, interval=60))
    await scheduler.tick(1000)
    saved = scheduler.list()[0]
    assert saved["due"] == 1060
    restarted = Scheduler(runtime.store, runtime.bus, runtime.tools.paths)
    await restarted.tick(1001)
    alerts = [e for e in runtime.store.events() if e["kind"] == "SYSTEM_ALERT"]
    assert len(alerts) == 1
    assert restarted.delete(record["id"])


async def test_file_watch(runtime):
    path = runtime.settings.workspace / "observed.txt"
    path.write_text("one")
    runtime.scheduler.add(
        ScheduleInput(title="File changed", due=100, kind="file_watch", path="observed.txt")
    )
    await runtime.scheduler.tick(100)
    assert not [e for e in runtime.store.events() if e["kind"] == "SYSTEM_ALERT"]
    path.write_text("different content")
    await runtime.scheduler.tick(160)
    assert len([e for e in runtime.store.events() if e["kind"] == "SYSTEM_ALERT"]) == 1
