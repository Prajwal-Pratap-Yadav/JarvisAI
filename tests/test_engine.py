import asyncio

import pytest
from pydantic import BaseModel

from jarvis.engine import Node, Plan, resolve_arguments
from jarvis.registry import Tool
from jarvis.tools import Empty


async def finish(runtime, plan):
    run = await runtime.engine.submit(plan)
    await runtime.engine.workers[run.id]
    return run


async def test_real_offline_demo(runtime):
    result = await runtime.demo()
    assert result["status"] == "completed"
    assert result["nodes"][0]["result"]["ram_total"] > 0
    assert result["validation"]["passed"]
    assert runtime.store.run(result["id"])["status"] == "completed"


@pytest.mark.parametrize(
    "nodes",
    [
        [Node(id="a", tool="system.status", dependencies=["missing"])],
        [
            Node(id="a", tool="system.status", dependencies=["b"]),
            Node(id="b", tool="system.status", dependencies=["a"]),
        ],
        [Node(id="a", tool="missing")],
        [Node(id="a", tool="system.status"), Node(id="a", tool="system.status")],
    ],
)
async def test_reject_invalid_graph(runtime, nodes):
    with pytest.raises(ValueError):
        await runtime.engine.submit(Plan(goal="bad", nodes=nodes))


async def test_bounded_parallel_execution(runtime):
    active = 0
    high = 0

    async def handler(args):
        nonlocal active, high
        active += 1
        high = max(active, high)
        await asyncio.sleep(0.02)
        active -= 1
        return {"value": 42}

    runtime.registry.register(Tool("test.parallel", "Test", "SYSTEM", "system", Empty, handler))
    run = await finish(
        runtime,
        Plan(goal="parallel", nodes=[Node(id=f"n{i}", tool="test.parallel") for i in range(10)]),
    )
    assert run.status == "completed"
    assert 1 < high <= 4


async def test_result_passing_and_validation(runtime):
    class Args(BaseModel):
        value: int

    async def first(args):
        return {"number": 7}

    async def second(args):
        return {"doubled": args["value"] * 2}

    runtime.registry.register(Tool("test.first", "First", "SYSTEM", "system", Empty, first))
    runtime.registry.register(Tool("test.second", "Second", "SYSTEM", "system", Args, second))
    run = await finish(
        runtime,
        Plan(
            goal="data flow",
            nodes=[
                Node(id="first", tool="test.first"),
                Node(
                    id="second",
                    tool="test.second",
                    arguments={"value": {"$ref": "first.number"}},
                    dependencies=["first"],
                    expect={"field": "doubled", "equals": 14},
                ),
            ],
        ),
    )
    assert run.status == "completed"
    assert run.nodes[1].result == {"doubled": 14}
    with pytest.raises(ValueError):
        resolve_arguments({"$ref": "first.number"}, {"first": {"number": 7}}, [])


async def test_failed_validation_blocks_dependents(runtime):
    run = await finish(
        runtime,
        Plan(
            goal="bad assertion",
            nodes=[
                Node(id="first", tool="files.list", expect={"field": "entries", "nonempty": True}),
                Node(id="second", tool="system.status", dependencies=["first"]),
            ],
        ),
    )
    assert run.status == "failed"
    assert run.nodes[0].status == "failed"
    assert run.nodes[1].status == "blocked"
    assert run.nodes[1].attempts == 0


async def test_retry_budget_and_recovery_events(runtime):
    count = 0

    async def flaky(args):
        nonlocal count
        count += 1
        if count < 2:
            raise ConnectionError("temporary")
        return {"ok": True}

    runtime.registry.register(
        Tool("test.retry", "retry", "SYSTEM", "system", Empty, flaky, retries=2)
    )
    run = await finish(
        runtime, Plan(goal="recover", nodes=[Node(id="a", tool="test.retry", retries=2)])
    )
    assert run.status == "completed" and count == 2
    assert "RECOVERY_STARTED" in [e["kind"] for e in runtime.store.events(run_id=run.id)]


async def test_timeout_and_cancel(runtime):
    async def wait(args):
        await asyncio.Event().wait()

    runtime.registry.register(Tool("test.wait", "wait", "SYSTEM", "system", Empty, wait))
    run = await finish(
        runtime, Plan(goal="timeout", nodes=[Node(id="a", tool="test.wait", timeout=0.05)])
    )
    assert run.status == "failed"
    run = await runtime.engine.submit(Plan(goal="cancel", nodes=[Node(id="a", tool="test.wait")]))
    await asyncio.sleep(0.01)
    await runtime.engine.cancel(run.id)
    assert run.status == "cancelled"
    assert run.nodes[0].status == "cancelled"


async def test_exact_action_approval_and_single_use(runtime):
    run = await finish(
        runtime,
        Plan(
            goal="write",
            nodes=[
                Node(
                    id="a",
                    tool="files.write",
                    arguments={"path": "report.md", "content": "A verified report."},
                )
            ],
        ),
    )
    assert run.status == "confirmation_required"
    assert not (runtime.settings.workspace / "report.md").exists()
    approval = next(iter(runtime.gate.pending.values()))
    await runtime.engine.decide(approval.id, True)
    await runtime.engine.workers[run.id]
    assert run.status == "completed"
    assert (runtime.settings.workspace / "report.md").read_text() == "A verified report."
    with pytest.raises(ValueError):
        await runtime.engine.decide(approval.id, True)


async def test_denial_blocks_dependent(runtime):
    run = await finish(
        runtime,
        Plan(
            goal="deny",
            nodes=[
                Node(id="a", tool="files.write", arguments={"path": "x", "content": "x"}),
                Node(id="b", tool="files.read", arguments={"path": "x"}, dependencies=["a"]),
            ],
        ),
    )
    approval = next(iter(runtime.gate.pending.values()))
    await runtime.engine.decide(approval.id, False)
    await runtime.engine.workers[run.id]
    assert run.status == "failed"
    assert run.nodes[1].status == "blocked"


async def test_execution_state_cannot_be_forged(runtime):
    run = await finish(
        runtime,
        Plan(
            goal="forgery",
            nodes=[
                Node(
                    id="a",
                    tool="files.read",
                    arguments={"path": "absent"},
                    status="completed",
                    result={"content": "fake"},
                )
            ],
        ),
    )
    assert run.status == "failed"
    assert run.nodes[0].result is None


async def test_restart_does_not_replay_effects(runtime):
    run = await finish(
        runtime,
        Plan(
            goal="pending write",
            nodes=[Node(id="a", tool="files.write", arguments={"path": "x", "content": "x"})],
        ),
    )
    await runtime.engine.recover_checkpoints()
    saved = runtime.store.run(run.id)
    assert saved["status"] == "interrupted"
    assert not (runtime.settings.workspace / "x").exists()
