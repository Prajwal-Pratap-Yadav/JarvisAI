# Baseline repository audit

The starting `main` commit was `989e6c4c8a9d6a4d865b2c6d9b9c5cc3f7727fcc` (one historical commit and one branch). Its 18,214 tracked paths consisted of `main.py` plus 18,213 paths under `venv/`. The only application source was an 831-byte Ollama/Rich chat loop using `phi3:mini`, without persistent context. No application tests, README, dependency declaration, CI, release configuration, or useful feature modules were present outside the virtual environment. No AGENTS.md was present.

The revision preserves that model option and the original Git history. It removes generated virtual-environment paths from the new tree instead of redistributing another machine's interpreter environment. It introduces application source, reproducible dependencies, generated-environment exclusions, documentation, and test/release tooling.

The local build environment was Linux x64 with Python 3.12 and Node 24. No exposed GPU, audio device, or graphical desktop was available. Direct Playwright Chromium downloads returned truncated archives and OS-package installation lacked required permissions. Those facts constrain local hardware/browser validation; no simulated results are substituted. The GitHub connection supplies repository read/write access, while the shell has no push credentials. New source publication uses the authenticated repository owner's identity.
