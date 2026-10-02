"""Bounded asynchronous DAG execution with durable checkpoints and exact-action gates."""

from __future__ import annotations

import asyncio
import copy
import time
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from jarvis.events import EventBus
from jarvis.registry import Registry
from jarvis.security import ApprovalGate, Denied, Unavailable, redact
from jarvis.storage import Store


class RuntimeState(StrEnum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    INTERPRETING = "INTERPRETING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    WAITING = "WAITING"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    RECOVERING = "RECOVERING"
    SELF_EVALUATING = "SELF_EVALUATING"
    SPEAKING = "SPEAKING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Node(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    parent_id: str | None = None
    priority: int = Field(default=0, ge=-10, le=10)
    retries: int = Field(default=0, ge=0, le=2)
    timeout: float = Field(default=30, ge=0.05, le=120)
    # Validation uses returned fields, not a model's assertion of success.
    expect: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"
    attempts: int = 0
    result: dict | None = None
    error: str | None = None
    duration: float = 0

    @field_validator("expect")
    @classmethod
    def valid_expectation(cls, value: dict) -> dict:
        if set(value) - {"field", "equals", "contains", "nonempty"}:
            raise ValueError("Unknown validation rule")
        return value


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    goal: str = Field(min_length=1, max_length=16000)
    nodes: list[Node] = Field(min_length=1, max_length=64)


class Run(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    goal: str
    nodes: list[Node]
    status: str = "pending"
    created: float = Field(default_factory=time.time)
    completed: float | None = None
    validation: dict | None = None


def field_value(data: Any, path: str) -> Any:
    for part in path.split(".") if path else []:
        data = data[int(part)] if isinstance(data, list) else data[part]
    return data


def resolve_arguments(value: Any, results: dict[str, Any], dependencies: list[str]) -> Any:
    if isinstance(value, dict):
        if set(value) == {"$ref"}:
            reference = value["$ref"]
            ident, _, path = reference.partition(".")
            if ident not in dependencies:
                raise ValueError("Result references must name an explicit dependency")
            return copy.deepcopy(field_value(results[ident], path))
        return {k: resolve_arguments(v, results, dependencies) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_arguments(v, results, dependencies) for v in value]
    return value


def validate_result(result: dict, required: tuple[str, ...], expect: dict) -> dict:
    if not isinstance(result, dict) or any(key not in result for key in required):
        raise ValueError("Tool output does not satisfy its output contract")
    if result.get("ok") is False:
        raise ValueError(str(result.get("detail", "Tool reported failure")))
    target = field_value(result, expect.get("field", ""))
    if "equals" in expect and target != expect["equals"]:
        raise ValueError("Validation failed: expected value mismatch")
    if "contains" in expect and expect["contains"] not in target:
        raise ValueError("Validation failed: required content is missing")
    if expect.get("nonempty") and not target:
        raise ValueError("Validation failed: empty result")
    return {"passed": True, "checks": ["output_contract", *expect.keys()]}


class Engine:
    def __init__(
        self,
        registry: Registry,
        store: Store,
        bus: EventBus,
        gate: ApprovalGate,
        concurrency: int = 4,
        max_nodes: int = 24,
    ):
        self.registry, self.store, self.bus, self.gate = registry, store, bus, gate
        self.semaphore = asyncio.Semaphore(concurrency)
        self.max_nodes = max_nodes
        self.runs: dict[str, Run] = {}
        self.workers: dict[str, asyncio.Task] = {}
        self.children: dict[str, set[asyncio.Task]] = {}

    def validate_plan(self, plan: Plan) -> None:
        if len(plan.nodes) > self.max_nodes:
            raise ValueError(f"Plan exceeds the {self.max_nodes}-node budget")
        nodes = {n.id: n for n in plan.nodes}
        if len(nodes) != len(plan.nodes):
            raise ValueError("Task IDs must be unique")
        for node in plan.nodes:
            self.registry.get(node.tool)
            if set(node.dependencies) - nodes.keys() or node.id in node.dependencies:
                raise ValueError("Missing or self-referential dependency")
            if node.parent_id and (node.parent_id not in nodes or node.parent_id == node.id):
                raise ValueError("Invalid parent task")
        visited: set[str] = set()
        active: set[str] = set()

        def visit(ident: str) -> None:
            if ident in active:
                raise ValueError("Task dependencies contain a cycle")
            if ident in visited:
                return
            active.add(ident)
            for dep in nodes[ident].dependencies:
                visit(dep)
            active.remove(ident)
            visited.add(ident)

        for ident in nodes:
            visit(ident)

    async def submit(self, plan: Plan) -> Run:
        self.validate_plan(plan)
        if (
            sum(
                r.status in {"pending", "running", "confirmation_required"}
                for r in self.runs.values()
            )
            >= 8
        ):
            raise Denied("Eight active runs already; wait or cancel a run")
        # Ignore supplied execution fields: clients and model plans cannot forge success.
        nodes = [
            Node(
                **{
                    k: v
                    for k, v in n.model_dump().items()
                    if k not in {"status", "attempts", "result", "error", "duration"}
                }
            )
            for n in plan.nodes
        ]
        # Keep only a bounded hot cache; older runs remain in SQLite.
        finished = [
            ident
            for ident, old in self.runs.items()
            if old.status not in {"pending", "running", "confirmation_required"}
        ]
        for ident in finished[:-100]:
            self.runs.pop(ident, None)
            self.workers.pop(ident, None)
        run = Run(goal=plan.goal, nodes=nodes)
        self.runs[run.id] = run
        self.checkpoint(run)
        await self.bus.publish("TASK_CREATED", {"goal": run.goal, "nodes": len(nodes)}, run.id)
        self.start(run)
        return run

    def start(self, run: Run) -> None:
        worker = self.workers.get(run.id)
        if worker and not worker.done():
            return
        self.workers[run.id] = asyncio.create_task(self.execute(run))

    def checkpoint(self, run: Run) -> None:
        self.store.save_run(run.model_dump())

    async def state(self, run: Run, state: str, **data: Any) -> None:
        await self.bus.publish("RUNTIME_STATE", {"state": state, **data}, run.id)

    async def node(self, run: Run, node: Node) -> None:
        tool = self.registry.get(node.tool)
        started = time.monotonic()
        try:
            results = {n.id: n.result for n in run.nodes}
            args = resolve_arguments(node.arguments, results, node.dependencies)
            args = tool.inputs.model_validate(args).model_dump()
            ready, reason = tool.available()
            if not ready:
                raise Unavailable(reason)
            if tool.confirmation or tool.risk != "low":
                if not self.gate.consume(run.id, node.id, tool.name, args):
                    approval = self.gate.request(run.id, node.id, tool.name, args)
                    node.status = "confirmation_required"
                    await self.bus.publish("CONFIRMATION_REQUIRED", approval.public(), run.id)
                    return
            attempts = 1 + min(node.retries, tool.retries) if tool.idempotent else 1
            async with self.semaphore:
                for attempt in range(attempts):
                    node.status = "running"
                    node.attempts += 1
                    self.checkpoint(run)
                    await self.bus.publish(
                        "AGENT_SWITCHED", {"agent": tool.agent, "node_id": node.id}, run.id
                    )
                    await self.bus.publish(
                        "TOOL_STARTED",
                        {"tool": tool.name, "node_id": node.id, "attempt": node.attempts},
                        run.id,
                    )
                    try:
                        result = await asyncio.wait_for(
                            tool.handler(args), min(node.timeout, tool.timeout)
                        )
                        await self.state(run, RuntimeState.SELF_EVALUATING, node_id=node.id)
                        validation = validate_result(result, tool.required_outputs, node.expect)
                        # Prevent plugins returning unbounded or non-JSON checkpoint payloads.
                        import json

                        if len(json.dumps(result)) > 200_000:
                            raise ValueError("Tool output exceeds the 200 KB result budget")
                        node.result = redact(result)
                        node.status = "completed"
                        node.error = None
                        await self.bus.publish(
                            "SELF_EVALUATION_COMPLETED", {"node_id": node.id, **validation}, run.id
                        )
                        await self.bus.publish(
                            "TOOL_COMPLETED", {"node_id": node.id, "tool": tool.name}, run.id
                        )
                        break
                    except (TimeoutError, ConnectionError, OSError) as exc:
                        if attempt + 1 >= attempts:
                            raise
                        await self.state(run, RuntimeState.RECOVERING, node_id=node.id)
                        await self.bus.publish(
                            "RECOVERY_STARTED",
                            {"node_id": node.id, "cause": type(exc).__name__, "retry": attempt + 1},
                            run.id,
                        )
                        await asyncio.sleep(0.1 * 2**attempt)
        except asyncio.CancelledError:
            node.status = "cancelled"
            node.error = "Execution cancelled; inspect external effects before retrying"
            raise
        except Exception as exc:
            node.status = "failed"
            # HTTP exceptions can contain credential-bearing URLs; report type plus safe text.
            node.error = (
                redact(str(exc)[:1000])
                if isinstance(exc, (ValueError, Unavailable, TimeoutError))
                else f"{type(exc).__name__}: operation failed"
            )
            await self.bus.publish("TOOL_FAILED", {"node_id": node.id, "error": node.error}, run.id)
        finally:
            node.duration += time.monotonic() - started
            self.checkpoint(run)

    async def execute(self, run: Run) -> None:
        running: dict[asyncio.Task, Node] = {}
        self.children[run.id] = set()
        run.status = "running"
        await self.state(run, RuntimeState.EXECUTING)
        try:
            while True:
                by_id = {n.id: n for n in run.nodes}
                for node in sorted(run.nodes, key=lambda n: -n.priority):
                    if node.status != "pending":
                        continue
                    parents = [by_id[d] for d in node.dependencies]
                    if any(
                        p.status in {"failed", "blocked", "cancelled", "interrupted"}
                        for p in parents
                    ):
                        node.status, node.error = "blocked", "A dependency did not complete"
                    elif all(p.status == "completed" for p in parents):
                        node.status = "queued"
                        task = asyncio.create_task(self.node(run, node))
                        running[task] = node
                        self.children[run.id].add(task)
                self.checkpoint(run)
                if not running:
                    break
                done, _ = await asyncio.wait(running, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    running.pop(task)
                    self.children[run.id].discard(task)
                    await task
                await self.bus.publish(
                    "TASK_PROGRESS",
                    {
                        "completed": sum(n.status == "completed" for n in run.nodes),
                        "total": len(run.nodes),
                    },
                    run.id,
                )
            if any(n.status == "confirmation_required" for n in run.nodes):
                run.status = "confirmation_required"
                await self.state(run, RuntimeState.CONFIRMATION_REQUIRED)
            else:
                passed = all(n.status == "completed" for n in run.nodes)
                run.status = "completed" if passed else "failed"
                run.completed = time.time()
                run.validation = {
                    "passed": passed,
                    "completed_nodes": sum(n.status == "completed" for n in run.nodes),
                    "total_nodes": len(run.nodes),
                    "scope": "Tool contracts and explicit expectations; not proof of real-world goal quality",
                }
                self.gate.clear_run(run.id)
                await self.bus.publish(
                    "TASK_COMPLETED" if passed else "TASK_FAILED",
                    {"validation": run.validation},
                    run.id,
                )
                await self.state(run, RuntimeState.COMPLETED if passed else RuntimeState.FAILED)
        except asyncio.CancelledError:
            for task in running:
                task.cancel()
            await asyncio.gather(*running, return_exceptions=True)
            for node in run.nodes:
                if node.status in {"pending", "queued", "confirmation_required"}:
                    node.status = "cancelled"
            run.status = "cancelled"
            run.completed = time.time()
            self.gate.clear_run(run.id)
            await self.bus.publish("USER_INTERRUPTED", {}, run.id)
        finally:
            self.children.pop(run.id, None)
            self.checkpoint(run)

    async def decide(self, approval_id: str, allowed: bool) -> Run:
        approval = self.gate.decide(approval_id, allowed)
        run = self.runs[approval.run_id]
        node = next(n for n in run.nodes if n.id == approval.node_id)
        # Wait for the coordinator to settle, preserving sibling approvals.
        worker = self.workers.get(run.id)
        if worker and not worker.done():
            await worker
        node.status = "pending" if allowed else "failed"
        node.error = None if allowed else "User denied this action"
        await self.bus.publish("APPROVAL_DECIDED", {"node_id": node.id, "allowed": allowed}, run.id)
        self.start(run)
        return run

    async def cancel(self, run_id: str) -> None:
        if run_id not in self.runs:
            raise ValueError("Unknown live run")
        task = self.workers.get(run_id)
        if task and not task.done():
            task.cancel()
            await task
        else:
            run = self.runs[run_id]
            for node in run.nodes:
                if node.status in {"pending", "confirmation_required"}:
                    node.status = "cancelled"
            run.status = "cancelled"
            self.gate.clear_run(run_id)
            self.checkpoint(run)

    async def recover_checkpoints(self) -> None:
        for raw in self.store.runs(1000):
            if raw["status"] in {"pending", "running", "confirmation_required"}:
                run = Run(**raw)
                run.status = "interrupted"
                for node in run.nodes:
                    if node.status != "completed":
                        node.status = "interrupted"
                        node.error = "Runtime restarted. Review effects and submit a new plan."
                self.checkpoint(run)
                await self.bus.publish(
                    "RECOVERY_REQUIRED",
                    {"detail": "Checkpoint recovered; no side effects automatically replayed"},
                    run.id,
                )

    async def close(self) -> None:
        for ident in list(self.workers):
            if not self.workers[ident].done():
                await self.cancel(ident)
