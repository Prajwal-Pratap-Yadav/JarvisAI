"""Cross-platform launcher for source, wheel, and frozen distributions."""

import argparse
import asyncio
import json
import threading
import webbrowser
from pathlib import Path

from jarvis import __version__
from jarvis.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="JARVIS AI — local personal AI runtime")
    parser.add_argument("command", nargs="?", choices=["serve", "doctor", "demo"], default="serve")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--port", type=int)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args()
    settings = Settings.load(args.data_dir)
    if args.port:
        settings = Settings(**{**settings.model_dump(), "port": args.port})
    if args.command in {"doctor", "demo"}:
        from jarvis.runtime import Runtime

        async def inspect():
            runtime = Runtime(settings)
            await runtime.start()
            try:
                return await (runtime.demo() if args.command == "demo" else runtime.diagnostics())
            finally:
                await runtime.close()

        result = asyncio.run(inspect())
        print(json.dumps(result, indent=2))
        if args.command == "demo" and result["status"] != "completed":
            raise SystemExit(1)
        return
    import uvicorn

    from jarvis.api import create_app

    url = f"http://127.0.0.1:{settings.port}/#token={settings.token()}"
    print(
        f"JARVIS AI {__version__}\nOpen this private local link:\n{url}\nKeep it private. Press Ctrl+C to stop.",
        flush=True,
    )
    if not args.no_browser:
        timer = threading.Timer(1.5, webbrowser.open, args=(url,))
        timer.daemon = True
        timer.start()
    uvicorn.run(
        create_app(settings),
        host="127.0.0.1",
        port=settings.port,
        log_level="warning",
        access_log=False,
        ws_max_size=8192,
    )


if __name__ == "__main__":
    main()
