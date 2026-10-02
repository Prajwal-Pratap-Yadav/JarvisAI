"""Real Chromium acceptance test. Run in CI after installing Playwright's Chromium."""

import asyncio
import os
import socket
import sys
import tempfile
from pathlib import Path

from playwright.async_api import async_playwright


async def main():
    with tempfile.TemporaryDirectory(prefix="jarvis-ui-") as folder:
        root = Path(folder)
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "jarvis.cli",
            "serve",
            "--no-browser",
            "--data-dir",
            str(root / "data"),
            "--port",
            str(port),
            env={
                **os.environ,
                "JARVIS_PROVIDER": "offline",
                "JARVIS_WORKSPACE": str(root / "work"),
            },
            stdout=asyncio.subprocess.DEVNULL,
        )
        try:
            for _ in range(100):
                if (root / "data/access.token").exists():
                    break
                await asyncio.sleep(0.1)
            token = (root / "data/access.token").read_text().strip()
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page(
                    viewport={"width": 1440, "height": 1150}, device_scale_factor=1
                )
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                await page.goto(f"http://127.0.0.1:{port}/#token={token}")
                await page.get_by_role("button", name="Save configuration").click()
                await page.get_by_role("button", name="Run system briefing").click()
                await page.get_by_text(
                    "Validation: tool contracts and declared expectations passed."
                ).wait_for(timeout=15000)
                await page.get_by_role("button", name="Memory", exact=False).first.click()
                await page.get_by_label("Approved knowledge").fill(
                    "<img src=x onerror=alert(1)> A user-approved preference."
                )
                await page.get_by_role("button", name="Save approved memory").click()
                await page.get_by_text(
                    "<img src=x onerror=alert(1)> A user-approved preference.", exact=True
                ).wait_for()
                assert await page.locator("#memories img").count() == 0
                await page.get_by_role("button", name="Mission control").click()
                await asyncio.to_thread(Path("test-results").mkdir, exist_ok=True)
                await page.screenshot(path="test-results/hud-desktop.png", full_page=True)
                await page.set_viewport_size({"width": 390, "height": 844})
                assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                await page.screenshot(path="test-results/hud-mobile.png", full_page=True)
                assert not errors, errors
                await browser.close()
                print(
                    "PASS: real Chromium launch, setup, task execution, memory, XSS rendering, responsive layout"
                )
        finally:
            process.terminate()
            await asyncio.wait_for(process.wait(), 10)


if __name__ == "__main__":
    asyncio.run(main())
