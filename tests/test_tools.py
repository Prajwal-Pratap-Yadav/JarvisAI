import asyncio
import sys

import pytest

from jarvis.processes import run_process
from jarvis.security import Denied


async def test_subprocess_bounded_output_and_failure(tmp_path):
    result = await run_process(
        [sys.executable, "-c", 'print("x"*80000);raise SystemExit(3)'], tmp_path
    )
    assert result["exit_code"] == 3
    assert result["truncated"] and len(result["output"]) == 60000
    with pytest.raises(TimeoutError):
        await run_process(
            [sys.executable, "-c", "import time;time.sleep(60)"], tmp_path, timeout=0.1
        )


async def test_code_search_excludes_environment_and_symlinks(runtime):
    (runtime.settings.workspace / "code.py").write_text("def useful_function(): pass")
    (runtime.settings.workspace / ".env").write_text("password=hidden")
    found = await runtime.tools.code_search({"path": ".", "query": "useful"})
    assert found["matches"][0]["path"] == "code.py"
    assert not (await runtime.tools.code_search({"path": ".", "query": "hidden"}))["matches"]


async def test_research_partial_failure_preserves_provenance(runtime, monkeypatch):
    async def read(url):
        if "bad" in url:
            raise Denied("blocked host")
        return {"url": url, "title": "Evidence", "text": "Source statement", "retrieved_at": 1}

    monkeypatch.setattr(runtime.tools.web, "read", read)
    result = await runtime.tools.research(
        {"question": "question", "urls": ["https://good.example", "https://bad.example"]}
    )
    assert result["source_count"] == 1
    assert result["sources"][0]["source_id"] == "S1"
    assert result["failures"][0]["url"] == "https://bad.example"
    synthesized = await runtime.tools.synthesize(
        {"goal": "question", "evidence": result["sources"]}
    )
    assert synthesized["method"] == "verbatim evidence compilation"


async def test_browser_blocks_posts(runtime):
    class Request:
        method = "POST"

    class Route:
        request = Request()
        aborted = False

        async def abort(self, reason):
            self.aborted = True

    route = Route()
    await runtime.tools.browser.route(route)
    assert route.aborted


async def test_registry_has_real_contracts(runtime):
    tools = runtime.registry.catalog()
    assert len(tools) >= 20
    for tool in tools:
        assert tool["input_schema"]["type"] == "object"
        assert tool["output_schema"]["type"] == "object"
        if tool["risk"] != "low":
            assert tool["confirmation"]
    graph = runtime.registry.graph()
    assert len(graph["edges"]) == len(tools)


async def test_no_uncontrolled_background_tasks(runtime):
    tasks = list(runtime.background)
    assert all(not task.done() for task in tasks)
    await asyncio.sleep(0.01)
