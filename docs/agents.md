# Agent contracts

| Role | Real responsibility |
|---|---|
| Core | Bounded conversation and response synthesis through a configured model |
| Planning | Generate typed plans using the discoverable capability catalog |
| Research | Collect public evidence and preserve attribution/failures |
| Coding | Inspect/search files, inspect Git, write with expected hashes, run approved tests |
| Vision | Capture an actual screen, run local OCR, or send an image to a configured model |
| Computer | Dispatch explicitly approved keyboard/mouse/clipboard operations |
| Browser | Isolated anonymous Playwright sessions with guarded GET-only networking |
| System | CPU, RAM, disk, network counters, uptime, and available GPU sensors |
| Memory | User-approved records, deduplication, retrieval, and controls |
| Security | Enforce paths, hosts, exact-action grants, and risk classification |
| Monitoring | Process observations, scheduler watches, and rate-limited alerts |
| Evaluation | Tool contracts, explicit assertions, and evidence assessment |
| Knowledge | Compose reports while retaining source metadata |

Agents share typed tools and the central execution engine. They are not thirteen independent model instances. This keeps authority and execution observable and prevents recursive agent-to-agent loops. The capability graph links each role to its actual tools; availability metadata explains missing packages or configuration.

A new tool supplies a Pydantic input model, an async handler returning JSON, required output keys, timeout, risk, confirmation, availability, and idempotency. Register it once with `Registry.register`. Write a behavior test and a policy test. The UI and planner discover the tool automatically; desktop or external effects must not be classified low risk merely to bypass approvals.
