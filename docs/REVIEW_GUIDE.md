# JARVIS AI local assistant runtime: review guide

Inspect explicit tool approval, storage, network policy, and auditable execution rather than treating an assistant demo as an autonomy claim.

## Follow the implementation

| Start here | File | What to inspect |
| --- | --- | --- |
| Execution engine | [jarvis/engine.py](../jarvis/engine.py) | Tool dispatch and execution state. |
| Security policy | [jarvis/security.py](../jarvis/security.py) | Approval and policy checks. |
| Network boundary | [jarvis/network.py](../jarvis/network.py) | Controlled network behavior. |
| Engine tests | [tests/test_engine.py](../tests/test_engine.py) | Execution and failure paths. |
| Security tests | [tests/test_security.py](../tests/test_security.py) | Policy and approval regression cases. |
| Audit | [docs/audit.md](../docs/audit.md) | Evidence for implemented capabilities and open boundaries. |

## Run the checks

Run from the repository root after the setup described in the [README](../README.md). Review fixtures and recorded evidence before starting any full experiment.

```bash
python -m pip install -e '.[dev]'
pytest --cov=jarvis -q
jarvis doctor
jarvis demo
```

## Interpret the evidence

Use the full setup and optional-dependency instructions in the root README. This is a local engineering preview with explicit capabilities. Approval policy is not an operating-system sandbox, and passing tests do not establish general intelligence or safe unrestricted autonomy.

The linked reports retain their original experiment dates and protocols. A new passing CI run verifies its named checks; it does not silently refresh historical measurements.

## Discuss the design

- Where is a requested plan separated from an approved tool execution?
- How are failed actions represented in the audit trail?
