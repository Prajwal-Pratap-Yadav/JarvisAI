# Development and release workflow

Use Python 3.11+ with a fresh virtual environment. Install `requirements.lock`, then `pip install -c requirements.lock -e ".[dev]"`. Run Ruff, mypy, pytest, the Node voice test, `scripts/security_scan.py`, and `scripts/smoke_package.py` as shown in the README. No frontend build tool is required; static modules ship as Python package data.

Tests use real SQLite and subprocesses plus mocked external model/network responses. Network/provider mocks are contracts, not evidence that a live account or hardware device was exercised. The separate `scripts/browser_smoke.py` requires an actual Playwright Chromium installation and checks setup, live tasks, memory rendering, XSS-safe text, and mobile width. CI screenshots are retained as artifacts.

`python -m build` creates the wheel and source archive. Install the wheel in a clean environment and run the smoke script from outside the repository so it cannot accidentally import the checkout. `scripts/build_portable.py` runs PyInstaller on the native target, includes assets/documentation/licenses, tests the built executable, writes build provenance, and produces a ZIP plus SHA-256 sidecar. Never cross-label an executable for another operating system.

The workflow publishes only after the Windows/Linux Python matrix, dependency audit, and real browser checks succeed. Packaging is done natively on both targets. The release tag points to `GITHUB_SHA`. Existing published versions are immutable: update `pyproject.toml`, `jarvis.__version__`, HUD version, changelog, and release notes for the next release. The release job uses its ephemeral GitHub Actions token with contents write permission only; source commits use the repository owner's identity.

Preserve the database, history, and user files during development. Do not run cleanup routines against the user's workspace. Optional adapters should degrade with `Unavailable`, never sample/fake responses. Avoid adding provider or desktop imports at core startup.
