# Cognitive loop and evaluation

The implemented loop is goal → capability-aware plan → dependency graph → approved action → observation → validation → complete or report failure. The model sees available tool contracts, not a fixed command list. JSON plans are parsed, validated, and executed without evaluating model-generated Python. Offline shortcuts are explicitly limited and do not pretend to provide general reasoning.

Working context is bounded to twelve messages per session and one hundred sessions. Approved memory can inform model conversation. Source pages and memory are labelled untrusted data, with instructions to ignore embedded commands. This reduces prompt-injection exposure but does not make language models immune. Enforcement comes from the separate policy layer, not from the prompt alone.

Self-evaluation checks output contracts, `ok:false`, explicit field expectations (`equals`, `contains`, `nonempty`), and a 200 KB output budget. File writes reread their output and compare SHA-256 hashes. Test execution treats nonzero exit codes and empty unittest discovery as failures. These checks establish measurable execution properties, not universal semantic correctness.

Read-only retries have per-tool and per-node budgets; mutation tools are not automatically retried. Timeout, cancellation, and process cleanup are explicit. Failure reports and event replay expose concise observations, not private model reasoning. User-initiated replanning receives prior observations and instructions to avoid repeated effects, but its result still needs normal approval.

AGI-oriented here means the architecture connects perception, memory, planning, action, and evaluation. It is not evidence of AGI. Neural semantic retrieval, autonomous cross-domain skill learning, automatic structural plan repair, and stronger independent evaluators remain research work.
