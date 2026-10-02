# Configuration

Settings in the HUD cover the provider, model, base URL, allowed network hosts, desktop availability, and proactive notifications. `settings.json` stores these values atomically. Credentials are read from the environment; `.env.example` documents names but is **not automatically loaded**.

| Setting | Purpose |
|---|---|
| `JARVIS_PROVIDER` | `offline`, `ollama`, or `compatible` |
| `JARVIS_MODEL` | Installed/provider model identifier; default `phi3:mini` |
| `JARVIS_MODEL_URL` | Ollama root URL or compatible `/v1` base URL |
| `JARVIS_API_KEY` | Optional compatible-provider credential |
| `BRAVE_API_KEY` | Optional Brave Search credential |
| `JARVIS_WORKSPACE` | Trusted file-tool root; restart after changing |
| `JARVIS_DATA_DIR` | Local settings/database/token directory |
| `JARVIS_PORT` | Local port, default 8765 |
| `JARVIS_NETWORK_HOSTS` | Exact comma-separated public hostnames, no wildcards |
| `JARVIS_DESKTOP_ENABLED` | `true` enables optional desktop adapters |
| `JARVIS_PROACTIVE` | `true` enables rate-limited RAM threshold alerts |

Ollama example: select `ollama`, use `http://127.0.0.1:11434`, and enter an installed model. Model installation and server startup are external prerequisites, never simulated. Compatible example: select `compatible`, enter an HTTPS provider base ending in `/v1`, configure a supported model and the environment key. Plain HTTP is accepted only on loopback.

Cloud providers receive prompts, selected memory, and supplied images. Selecting a cloud model is a data-sharing decision. The Settings form never returns environment secret values. No provider fallback occurs without changing configuration. The current API uses nonstreaming chat completions; not every vendor/model supports JSON plans or images.

Concurrency, node budgets, history days, and the optional embedding model are advanced `settings.json` fields. The embedding adapter is not yet integrated with memory retrieval. Run one server per data directory. Server host cannot be changed to a public address through the CLI.
