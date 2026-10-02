# Architecture and lifecycle

`Runtime` owns one SQLite connection, an event bus, memory, model gateway, tool registry, policy gate, DAG engine, planner, scheduler, and telemetry sampler. FastAPI's lifespan creates and closes these resources. Background tasks are cancelled and awaited on shutdown. A single local server process owns the database and scheduler; multi-user hosting is not supported.

`Plan` is validated before execution: unique IDs, bounded node count, known tools, declared dependencies, no cycles. Independent nodes can run concurrently, with a global four-slot semaphore by default. Up to eight live runs may exist. High-priority ready nodes are queued first. This is bounded task scheduling, not hard real-time scheduling or preemption.

Nodes execute in the order: resolve dependency references → validate typed inputs → check availability → request exact-action approval when needed → acquire capacity → execute with deadline → validate observed outputs → checkpoint. Effects cannot be approved through model output. Failed nodes block dependents while independent siblings can finish. A failed required node prevents the run from being labelled complete.

The event bus writes to SQLite before notifying bounded subscribers. Slow clients do not hold workers; the HUD reconnects by sequence number and fetches replay gaps. Initial live subscriptions receive at most the latest 200 historical events. The dedicated replay endpoint selects a run's trace. Retention prunes old events/runs at startup and hourly.

SQLite uses WAL and parameterized statements. Durable checkpoints recover interrupted work for inspection. They do not replay file writes, tests, or desktop actions after a crash. An explicit model replan creates a new linked run; all approvals apply again. Replanning is user initiated in this preview.

Modules are deliberately substantive rather than one empty package per requested noun. `tools.py` contains the concrete capability adapters; `engine.py` controls execution; `security.py` controls authority; `models.py` handles provider protocols; the remaining files own persistence, UI delivery, and lifecycle.
