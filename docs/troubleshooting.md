# Troubleshooting

- **Unauthorized / disconnected HUD:** open the current private launch URL from the server console in the same browser tab. Do not remove its fragment before the app reads it. Stop other instances using the same port.
- **No language model selected:** offline mode supports tools, not general chat. Select a running provider and an installed model. Doctor distinguishes endpoint reachability from the selected model being present.
- **Ollama connection refused:** start your Ollama server independently and verify its model list. No model weights or GPU service are bundled.
- **Provider rejects JSON or images:** use a model that supports the required modality/protocol. Inspect the task error; a text-only model cannot analyze an image.
- **Research host blocked:** add the exact public hostname in Settings, including legitimate redirect/CDN hosts. Private/internal URLs remain blocked.
- **Browser configured but fails on launch:** install the Playwright browser binaries and OS dependencies. Package import detection does not guarantee a browser binary exists.
- **No microphone / speech recognition:** use a supported browser with microphone permission and a functioning device. Some browsers rely on a remote speech service. Typing remains available.
- **Desktop unavailable:** install optional packages, enable desktop access, and use a graphical OS session. Headless execution cannot capture your personal computer's screen.
- **File write rejected:** read the existing file and use its SHA-256 as `expected_sha256`; review a new approval. Never remove this check to force an overwrite.
- **Interrupted task after restart:** inspect completed effects. Submit a new graph or choose model replanning; the system will not silently repeat external effects.
- **Portable app exits:** extract the complete archive, keep `_internal`, and launch from a console for a readable error. Only use a package built for your OS/architecture.
- **Reminder did not fire:** the server must be running. After restart, one missed recurring occurrence is dispatched and the next deadline advances; there is no catch-up flood.
