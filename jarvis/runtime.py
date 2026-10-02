"""Central lifecycle and state composition, including graceful resource shutdown."""

import asyncio
import importlib.util
import platform
import time

from jarvis import __version__
from jarvis.config import Settings
from jarvis.engine import Engine, Plan, RuntimeState
from jarvis.events import EventBus
from jarvis.memory import Memory
from jarvis.models import ModelGateway
from jarvis.planning import Planner, agents
from jarvis.registry import Registry, Tool
from jarvis.scheduler import ScheduleInput, Scheduler
from jarvis.security import ApprovalGate
from jarvis.storage import Store
from jarvis.telemetry import Telemetry
from jarvis.tools import Builtins


class Runtime:
    def __init__(self, settings: Settings):
        self.settings = settings
        settings.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        settings.workspace.mkdir(parents=True, exist_ok=True)
        self.store = Store(settings.data_dir / "jarvis.db")
        self.bus = EventBus(self.store)
        self.memory = Memory(self.store)
        self.model = ModelGateway(settings)
        self.telemetry = Telemetry(settings.workspace)
        self.tools = Builtins(settings, self.memory, self.model, self.telemetry)
        self.registry = Registry()
        self.tools.register(self.registry)
        self.gate = ApprovalGate()
        self.engine = Engine(
            self.registry, self.store, self.bus, self.gate, settings.concurrency, settings.max_nodes
        )
        self.planner = Planner(self.registry, self.model)
        self.scheduler = Scheduler(self.store, self.bus, self.tools.paths)

        async def schedule(args: dict) -> dict:
            return self.scheduler.add(ScheduleInput(**args))

        self.registry.register(
            Tool(
                "scheduler.remind",
                "Create a persistent reminder or file/process watch",
                "SCHEDULER",
                "monitoring",
                ScheduleInput,
                schedule,
                risk="medium",
                idempotent=False,
                required_outputs=("id", "due"),
            )
        )
        self.background: list[asyncio.Task] = []
        self.planning_lock = asyncio.Semaphore(2)

    async def start(self) -> None:
        self.store.prune(self.settings.history_days)
        await self.engine.recover_checkpoints()
        await self.bus.publish(
            "RUNTIME_STATE", {"state": RuntimeState.IDLE, "version": __version__}
        )
        self.background = [
            asyncio.create_task(self.scheduler.loop()),
            asyncio.create_task(self.monitor()),
        ]

    async def monitor(self) -> None:
        last_alert = 0.0
        last_prune = time.monotonic()
        while True:
            await asyncio.sleep(15)
            measurement = await self.telemetry.sample()
            await self.bus.publish("SYSTEM_METRICS", measurement)
            if (
                self.settings.proactive
                and time.monotonic() - last_alert > 300
                and measurement["ram_percent"] > 90
            ):
                await self.bus.publish(
                    "SYSTEM_ALERT",
                    {"title": "Memory usage exceeds 90%", "kind": "resource_threshold"},
                )
                last_alert = time.monotonic()
            if time.monotonic() - last_prune > 3600:
                self.store.prune(self.settings.history_days)
                last_prune = time.monotonic()

    async def goal(self, goal: str, session: str) -> dict:
        async with self.planning_lock:
            await self.bus.publish("RUNTIME_STATE", {"state": RuntimeState.PLANNING})
            try:
                plan = await self.planner.plan(goal, session=session)
                self.engine.validate_plan(plan)
                await self.bus.publish(
                    "PLAN_CREATED", {"goal": goal, "tools": [n.tool for n in plan.nodes]}
                )
                return (await self.engine.submit(plan)).model_dump()
            except Exception:
                await self.bus.publish(
                    "RUNTIME_STATE",
                    {"state": RuntimeState.FAILED, "detail": "Planning could not complete"},
                )
                raise

    async def replan(self, run_id: str) -> dict:
        run = self.store.run(run_id)
        if not run or run["status"] not in {"failed", "interrupted", "cancelled"}:
            raise ValueError("Only failed, interrupted, or cancelled runs can be replanned")
        async with self.planning_lock:
            await self.bus.publish(
                "RECOVERY_STARTED", {"previous_run": run_id, "mode": "reviewed replan"}
            )
            plan = await self.planner.plan(run["goal"], failures=run)
            self.engine.validate_plan(plan)
            result = await self.engine.submit(plan)
            await self.bus.publish("RECOVERY_LINKED", {"previous_run": run_id}, result.id)
            return result.model_dump()

    async def diagnostics(self) -> dict:
        model = await self.model.health()
        desktop = self.tools.desktop_available()
        return {
            "version": __version__,
            "platform": platform.system(),
            "python": platform.python_version(),
            "core": {"available": True, "detail": "Runtime active"},
            "memory": {
                "available": True,
                "detail": "SQLite connected; user-controlled persistence",
            },
            "model": model,
            "browser": {
                "available": self.tools.browser.available()[0],
                "detail": self.tools.browser.available()[1],
            },
            "computer": {"available": desktop[0], "detail": desktop[1]},
            "vision": {
                "available": importlib.util.find_spec("PIL") is not None,
                "detail": "Image analysis also requires a vision-capable model; OCR requires Tesseract",
            },
            "audio": {
                "available": None,
                "detail": "Microphone and speech support are detected in your browser after consent",
            },
            "telemetry": await self.telemetry.sample(),
            "agents": agents(self.registry),
        }

    async def close(self) -> None:
        for task in self.background:
            task.cancel()
        await asyncio.gather(*self.background, return_exceptions=True)
        await self.engine.close()
        await self.tools.close()
        await self.model.close()
        self.store.close()

    async def demo(self) -> dict:
        """A real offline demo: parallel measurements, file listing, and verified policy."""
        plan = Plan.model_validate(
            {
                "goal": "Inspect this machine and workspace",
                "nodes": [
                    {
                        "id": "system",
                        "tool": "system.status",
                        "expect": {"field": "ram_total", "nonempty": True},
                    },
                    {"id": "files", "tool": "files.list"},
                    {"id": "policy", "tool": "security.policy"},
                ],
            }
        )
        run = await self.engine.submit(plan)
        await self.engine.workers[run.id]
        return run.model_dump()
