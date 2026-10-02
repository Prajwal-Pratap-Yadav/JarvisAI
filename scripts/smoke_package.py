"""Install-independent acceptance check: demo, configure, launch, persist, restart."""

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", type=Path)
    args = parser.parse_args()
    command = (
        [str(args.executable.resolve())]
        if args.executable
        else [sys.executable, "-m", "jarvis.cli"]
    )
    with tempfile.TemporaryDirectory(prefix="jarvis-smoke-") as folder:
        root = Path(folder)
        data = root / "data"
        env = {**os.environ, "JARVIS_WORKSPACE": str(root / "work"), "JARVIS_PROVIDER": "offline"}
        demo = subprocess.run(
            [*command, "demo", "--data-dir", str(data)],
            env=env,
            capture_output=True,
            text=True,
            timeout=40,
            check=True,
        )
        assert json.loads(demo.stdout)["status"] == "completed"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        token = None
        for cycle in range(2):
            process = subprocess.Popen(
                [*command, "serve", "--no-browser", "--port", str(port), "--data-dir", str(data)],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            try:
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError("Packaged server exited before becoming ready")
                    if (data / "access.token").exists():
                        current = (data / "access.token").read_text().strip()
                        if token is not None:
                            assert current == token, "Authentication changed after restart"
                        token = current
                        try:
                            request = urllib.request.Request(
                                base + "/api/status", headers={"Authorization": f"Bearer {token}"}
                            )
                            with urllib.request.urlopen(request, timeout=1) as response:
                                assert response.status == 200
                            break
                        except (urllib.error.URLError, TimeoutError):
                            pass
                    time.sleep(0.1)
                else:
                    raise RuntimeError("Packaged server never became ready")
                with urllib.request.urlopen(base, timeout=5) as response:
                    assert b"COGNITIVE CORE" in response.read()
                for asset in ["app.js", "style.css", "voice.js", "mark.svg"]:
                    with urllib.request.urlopen(base + "/assets/" + asset, timeout=5) as response:
                        assert len(response.read()) > 50

                def call(path, body=None, auth_token=token):
                    request = urllib.request.Request(
                        base + path,
                        data=json.dumps(body).encode() if body is not None else None,
                        headers={
                            "Authorization": f"Bearer {auth_token}",
                            "Content-Type": "application/json",
                        },
                    )
                    with urllib.request.urlopen(request, timeout=10) as response:
                        return json.load(response)

                if cycle == 0:
                    call(
                        "/api/memory",
                        {
                            "content": "Persisted package smoke-check memory",
                            "source": "package-test",
                        },
                    )
                else:
                    assert len(call("/api/memory")) == 1, "Memory did not survive restart"
                run = call("/api/goals", {"goal": "system status"})
                for _ in range(100):
                    observed = call("/api/runs/" + run["id"])
                    if observed["status"] == "completed":
                        break
                    time.sleep(0.05)
                assert observed["status"] == "completed"
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        print("PASS: demo, assets, authentication, live task, persistence, shutdown, restart")


if __name__ == "__main__":
    main()
