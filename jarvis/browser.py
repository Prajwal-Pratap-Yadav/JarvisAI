"""Optional isolated Playwright sessions; all HTTP traffic uses the guarded fetcher."""

from __future__ import annotations

import asyncio
import importlib.util
import uuid
from typing import Any

from jarvis.network import Web
from jarvis.security import Denied, Unavailable


class Browser:
    def __init__(self, web: Web):
        self.web = web
        self.driver: Any = None
        self.browser: Any = None
        self.sessions: dict[str, tuple[Any, Any]] = {}
        self.lock = asyncio.Lock()

    def available(self) -> tuple[bool, str]:
        ready = importlib.util.find_spec("playwright") is not None
        return (
            ready,
            "Playwright installed; browser binary checked on launch"
            if ready
            else "Install the browser extra and run playwright install chromium",
        )

    async def start(self) -> None:
        if not self.available()[0]:
            raise Unavailable(self.available()[1])
        if self.browser:
            return
        from playwright.async_api import async_playwright

        self.driver = await async_playwright().start()
        try:
            self.browser = await self.driver.chromium.launch(headless=True)
        except Exception as exc:
            await self.driver.stop()
            self.driver = None
            raise Unavailable(
                "Chromium cannot start. Install the Playwright browser binaries and OS dependencies."
            ) from exc

    async def route(self, route) -> None:
        if route.request.method != "GET":
            await route.abort("blockedbyclient")
            return
        try:
            _, mime, body = await asyncio.to_thread(
                self.web.fetch_bytes, route.request.url, 2_000_000
            )
            await route.fulfill(status=200, body=body, content_type=mime)
        except Exception:
            await route.abort("blockedbyclient")

    async def control(self, args: dict) -> dict:
        async with self.lock:
            await self.start()
            ident = args.get("session_id")
            if not ident:
                if len(self.sessions) >= 4:
                    raise Denied("Close a browser session before opening another (limit 4)")
                context = await self.browser.new_context(
                    accept_downloads=False, service_workers="block"
                )
                await context.route("**/*", self.route)
                await context.route_web_socket("**/*", lambda ws: ws.close())
                page = await context.new_page()
                page.set_default_timeout(8000)
                ident = uuid.uuid4().hex
                self.sessions[ident] = (context, page)
            if ident not in self.sessions:
                raise ValueError("Unknown browser session")
            context, page = self.sessions[ident]
            try:
                operation = args["operation"]
                if operation == "close":
                    await context.close()
                    self.sessions.pop(ident)
                    return {"session_id": ident, "closed": True, "text": "Session closed"}
                if operation == "navigate":
                    await asyncio.to_thread(self.web.validate, args["url"])
                    await page.goto(args["url"], wait_until="domcontentloaded", timeout=25000)
                elif operation in {"click", "fill"}:
                    # Prefer accessible roles; exact text fallback is explicit and bounded.
                    locator = page.get_by_role(
                        args.get("role", "button"), name=args["name"], exact=True
                    )
                    if await locator.count() == 0:
                        locator = page.get_by_text(args["name"], exact=True)
                    if await locator.count() != 1:
                        raise ValueError(
                            "Target is missing or ambiguous; inspect the page and replan"
                        )
                    if operation == "click":
                        await locator.click()
                    else:
                        await locator.fill(args.get("value", ""))
                elif operation != "extract":
                    raise ValueError("Unsupported browser operation")
                return {
                    "session_id": ident,
                    "url": page.url,
                    "title": await page.title(),
                    "text": (await page.locator("body").inner_text())[:20000],
                    "links": await page.locator("a[href]").evaluate_all(
                        "els => els.slice(0,50).map(e => ({text:e.innerText.slice(0,150),url:e.href}))"
                    ),
                    "trust": "untrusted_external_content",
                }
            except BaseException:
                # Failed sessions are closed so repeated navigation failures cannot leak contexts.
                await context.close()
                self.sessions.pop(ident, None)
                raise

    async def close(self) -> None:
        if self.browser:
            await self.browser.close()
        if self.driver:
            await self.driver.stop()
        self.browser = self.driver = None
        self.sessions.clear()
