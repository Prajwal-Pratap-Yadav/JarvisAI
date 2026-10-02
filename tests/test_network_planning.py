import socket

import pytest

from jarvis.engine import Node, Plan
from jarvis.network import Extractor, Web
from jarvis.security import Denied


def test_text_extraction_removes_scripts():
    parser = Extractor()
    parser.feed(
        "<html><title>Actual title</title><script>untrusted()</script><p>Evidence</p></html>"
    )
    assert parser.title == ["Actual title"]
    assert "untrusted()" not in parser.parts
    assert "Evidence" in parser.parts


def test_guarded_fetch_redirect_and_byte_budget(monkeypatch):
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("93.184.216.34", 443))]
    )
    visited = []

    class Response:
        status = 200

        def __init__(self, data):
            self.data = data

        def getheader(self, name, default=None):
            return "text/plain" if name == "Content-Type" else default

        def read(self, size):
            data, self.data = self.data[:size], self.data[size:]
            return data

    class Connection:
        def __init__(self, host, ip, timeout):
            visited.append((host, ip))

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            return Response(b"actual bytes")

        def close(self):
            pass

    monkeypatch.setattr("jarvis.network.PinnedHTTPS", Connection)
    result = Web(["example.com"]).fetch_bytes("https://example.com")
    assert result[2] == b"actual bytes"
    assert visited == [("example.com", "93.184.216.34")]
    with pytest.raises(ValueError):
        Web(["example.com"]).fetch_bytes("https://example.com", limit=5)

    class Redirect(Response):
        status = 302

        def getheader(self, name, default=None):
            return "https://blocked.example/secret"

    monkeypatch.setattr(Connection, "getresponse", lambda self: Redirect(b""))
    with pytest.raises(Denied):
        Web(["example.com"]).fetch_bytes("https://example.com")


async def test_planner_uses_catalog_and_validates_model_result(runtime, monkeypatch):
    runtime.settings.provider = "ollama"

    async def model(messages, **kwargs):
        assert "system.status" in messages[0]["content"]
        assert "Do not grant approvals" in messages[0]["content"]
        return '{"goal":"status","nodes":[{"id":"status","tool":"system.status"}]}'

    monkeypatch.setattr(runtime.model, "chat", model)
    plan = await runtime.planner.plan("Please inspect this machine")
    runtime.engine.validate_plan(plan)
    assert plan.nodes[0].tool == "system.status"


async def test_multiple_approvals_settle_without_repeating_writes(runtime):
    run = await runtime.engine.submit(
        Plan(
            goal="two writes",
            nodes=[
                Node(id="first", tool="files.write", arguments={"path": "a", "content": "one"}),
                Node(id="second", tool="files.write", arguments={"path": "b", "content": "two"}),
            ],
        )
    )
    await runtime.engine.workers[run.id]
    approvals = list(runtime.gate.pending)
    await runtime.engine.decide(approvals[0], True)
    await runtime.engine.workers[run.id]
    assert run.status == "confirmation_required"
    await runtime.engine.decide(approvals[1], True)
    await runtime.engine.workers[run.id]
    assert run.status == "completed"
    assert [n.attempts for n in run.nodes] == [1, 1]


@pytest.mark.parametrize("path", ["..\\escape", "C:stream", "\\\\host\\file"])
def test_windows_path_aliases_are_rejected(runtime, path):
    with pytest.raises(Denied):
        runtime.tools.paths.resolve(path)
