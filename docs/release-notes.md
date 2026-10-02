# JARVIS AI v0.1.0 — Engineering Preview

This first platform release replaces the minimal Ollama chat loop with a modular, local-first runtime. It removes the committed virtual environment from the current source tree while preserving Git history and adds reproducible dependencies, governed task execution, memory, research/coding tools, optional multimodal adapters, an original mission-control HUD, documentation, and release gates.

## Downloads and first run

Choose the native Windows x64 or Linux x64 portable ZIP, extract the complete folder, and launch JarvisAI. The console prints a private localhost link. Save first-run settings and select **Run system briefing** for an actual offline demonstration. Python 3.11+ users may install the wheel; source is also included. Portable packages include build metadata and SHA-256 sidecars.

## What is verified by this release workflow

Publishing is gated on Windows/Linux tests, lint/type/security/dependency checks, wheel installation and restart, real Chromium UI checks, and native executable smoke tests. The tag targets the workflow's exact source commit. No cloud model, GPU, microphone, desktop automation hardware, or research account is claimed verified by those gates.

## Known limitations

Engineering preview, not AGI. No model weights or provider credentials are bundled. Optional browser/desktop/OCR packages require the Python installation and extra setup. Browser automation is anonymous GET-only. Voice relies on browser recognition/TTS and is not guaranteed offline. Memory retrieval is lexical. Replanning is explicit. Project tests run with OS authority after approval. Local task history is plaintext; redaction cannot identify all sensitive data. Windows executables are unsigned; there is no installer or auto-updater.

See `docs/status.md` for the detailed capability matrix and `docs/security.md` for trust boundaries.
