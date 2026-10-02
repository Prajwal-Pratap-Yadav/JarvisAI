# Installation and updates

The primary end-user target is Windows x64. Native portable archives are produced on the corresponding operating system and smoke-tested before the release job attaches them. Linux x64 is also packaged. There is no signed installer or automatic updater in this preview; do not represent a Linux executable as a Windows build. Windows may show SmartScreen for an unsigned executable.

The wheel supports Python 3.11 and later; CI checks 3.11/3.12. Install a released wheel with `python -m pip install <wheel-file>`, then run `jarvis`. Source installations use a fresh virtual environment and `pip install -r requirements.lock`, followed by `pip install -e .`. Python and Node are developer prerequisites; Node is used only for the frontend module test and is not needed to run Jarvis.

To update a portable installation, stop the server, verify the downloaded SHA-256 checksum against the release asset, extract into a new folder, and launch the new executable. Data lives outside the application folder. Back up the data directory first. v0.1.0 has schema version 1 and no migration from other products.

On Windows, data defaults to `%LOCALAPPDATA%\JarvisAI`; on Linux/macOS, `$XDG_DATA_HOME/JarvisAI` or `~/.local/share/JarvisAI`. `--data-dir` or `JARVIS_DATA_DIR` changes this location. The data includes `settings.json`, `access.token`, and `jarvis.db`. Protect the directory with OS access permissions.
