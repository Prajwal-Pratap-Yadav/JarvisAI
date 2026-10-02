# Implementation and verification status

This release is a working engineering preview, not completion of every ambitious research target in the original brief.

| Area | Implemented | Limits / validation boundary |
|---|---|---|
| Core and states | Lifecycle, events, conversation context, tools, model routing | One local owner process |
| Task graph | DAGs, result references, concurrency, priorities, retries, deadlines, cancellation, checkpoints | No automatic replay of effects; model replanning is user initiated |
| Agents | Thirteen role contracts backed by planning, policy, evaluation, monitoring, and tools | Not thirteen autonomous model processes |
| Memory | Six conceptual layers; five persistent types, provenance, confidence, dedup, updates, deletion | Lexical retrieval; embedding adapter not connected to vector storage |
| Evaluation | Contracts, field assertions, byte verification, test exit status | Not proof of semantic correctness |
| Research | Source collection/search adapter, attribution, bounded parallel fetches, synthesis | Live search/model account requires credentials; contradictions model-assessed |
| Browser | Playwright navigation, extraction, sessions, accessible target fallback | Optional install; anonymous GET-only; no downloads/login/imported sessions |
| Voice | Browser recognition, transcript wake phrase, silence/RMS, TTS, interruption | No bundled local STT/TTS; browser/device-dependent; default mic/voice |
| Vision | Actual screenshot, local OCR, image model adapter | Optional dependencies/hardware/model; no robust coordinate grounding |
| Computer | Approved click/type/hotkey/clipboard/position | No app/window management, destructive commands, or external messaging |
| Coding | Search, read/write, Git status, approved pytest/unittest, result inspection | User-initiated fixes/plans; no container sandbox |
| Scheduler | Reminders, recurrence, file/process watches | No autonomous scheduled arbitrary action graphs |
| Proactive mode | Rate-limited memory-pressure alerts | No generalized external system-event ingestion |
| HUD | Live core, active role indicator, cognitive stages, node dependencies/results, replay, telemetry | Active-agent label rather than a full spatial multi-agent orbit |
| Packaging | Wheel/sdist, native portable build scripts, install/restart smoke gate | No signed Windows installer; native artifacts only published after CI success |
| AGI-oriented work | Integrated perception/memory/planning/action/evaluation boundaries | No AGI claim; no fabricated intelligence or performance benchmark |

Local verification uses automated core/security/integration tests, a real offline demo, source/wheel/native Linux smoke checks when available, static analysis, and dependency scanning. Live model, real audio/desktop, and Windows tests require their actual environments. CI is configured to perform Windows and real browser gates; a configured workflow is not itself evidence of a passing run. Check the linked run/release for current status.
