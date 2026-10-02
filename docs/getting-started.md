# First run

1. Download the native portable archive from Releases, extract the entire folder, and open `JarvisAI.exe` on Windows or `JarvisAI` on Linux. Keep `_internal` beside the executable. The package does not require a separate Python installation.
2. Jarvis opens its authenticated localhost link. If your browser does not open, use the link printed in the console. Do not share that link or its token.
3. Save the first-run settings. **Offline tools only** is a working mode, not a fake language model. You can configure an already-running Ollama server or compatible API later.
4. Select **System check**. Missing audio, browser binaries, desktop packages, GPU hardware, or models are shown as unavailable or requiring browser checks.
5. Click **Run system briefing**. Inspect CPU/memory measurements, the two independent task nodes, and their verified outputs. Try `list files` and `security policy`.
6. The default workspace is `JarvisWorkspace` in your home directory. Put a trusted project or text files there before using coding/file tools. The app does not expose your entire filesystem.
7. Use Memory to explicitly save preferences; use Schedules for reminders. Enable voice only if you consent to the browser's speech service. Approve exact writes or computer actions only after reviewing their arguments.

Close the server with Ctrl+C, then launch it again. Settings and persistent memory survive restart. A cancelled or interrupted task does not silently resume its side effects.
