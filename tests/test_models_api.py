import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from jarvis.api import create_app
from jarvis.config import Settings
from jarvis.models import ModelGateway, parse_json
from jarvis.security import Unavailable


@pytest.mark.parametrize(
    "url", ["http://remote.example", "https://u:p@example.com", "https://example.com?token=x"]
)
def test_unsafe_provider_urls(url):
    with pytest.raises(ValueError):
        Settings(model_url=url)


def test_settings_persistence(tmp_path, monkeypatch):
    for key in ["JARVIS_PROVIDER", "JARVIS_MODEL"]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("JARVIS_WORKSPACE", str(tmp_path / "work"))
    settings = Settings.load(tmp_path)
    settings.model = "custom-model"
    settings.save()
    assert Settings.load(tmp_path).model == "custom-model"
    assert settings.token() == settings.token()


async def test_model_protocol_ollama_and_compatible(tmp_path):
    requests = []

    async def response(request):
        body = json.loads(request.content)
        requests.append(body)
        if request.url.path == "/api/chat":
            return httpx.Response(200, json={"message": {"content": "observed result"}})
        return httpx.Response(200, json={"choices": [{"message": {"content": "vision response"}}]})

    for provider in ["ollama", "compatible"]:
        gateway = ModelGateway(Settings(provider=provider, data_dir=tmp_path))
        await gateway.client.aclose()
        gateway.client = httpx.AsyncClient(transport=httpx.MockTransport(response))
        result = await gateway.chat(
            [{"role": "user", "content": "analyze", "images": ["YWJj"]}], json_mode=True
        )
        assert result
        if provider == "compatible":
            assert requests[-1]["messages"][0]["content"][1]["type"] == "image_url"
        else:
            assert requests[-1]["format"] == "json"
        await gateway.close()


async def test_offline_is_not_fake_model(tmp_path):
    gateway = ModelGateway(Settings(data_dir=tmp_path))
    with pytest.raises(Unavailable):
        await gateway.chat([{"role": "user", "content": "hello"}])
    await gateway.close()


def test_bad_model_json():
    with pytest.raises(ValueError):
        parse_json("I executed your command")
    with pytest.raises(ValueError):
        parse_json("[]")


def test_api_auth_origin_and_real_run(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", workspace=tmp_path / "work")
    app = create_app(settings)
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        assert client.get("/api/status").status_code == 401
        client.headers["Authorization"] = f"Bearer {settings.token()}"
        assert (
            client.get("/api/status", headers={"Origin": "https://hostile.example"}).status_code
            == 403
        )
        assert client.get("/api/status", headers={"Host": "hostile.example"}).status_code == 403
        assert client.get("/").status_code == 200
        assert "script-src 'self'" in client.get("/").headers["content-security-policy"]
        assert client.get("/assets/app.js").status_code == 200
        response = client.post("/api/goals", json={"goal": "system status"})
        assert response.status_code == 200
        run_id = response.json()["id"]
        for _ in range(100):
            run = client.get(f"/api/runs/{run_id}").json()
            if run["status"] == "completed":
                break
        assert run["status"] == "completed"
        assert client.post("/api/goals", json={"goal": "Unconfigured chat"}).status_code == 503
        memory = client.post("/api/memory", json={"content": "I prefer Python"}).json()
        assert client.get("/api/memory?query=Python").json()[0]["id"] == memory["id"]
        assert client.delete(f"/api/memory/{memory['id']}").json()["deleted"]
        assert (
            client.post(
                "/api/plans", json={"goal": "bad", "nodes": [{"id": "x", "tool": "nonexistent"}]}
            ).status_code
            == 422
        )
        response = client.put(
            "/api/settings",
            json={
                "provider": "offline",
                "model": "phi3:mini",
                "model_url": "http://127.0.0.1:11434",
                "network_hosts": ["example.com"],
            },
        )
        assert response.status_code == 200
        assert client.get("/api/settings").json()["setup_complete"]


def test_request_limit_and_websocket_auth(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", workspace=tmp_path / "work")
    app = create_app(settings)
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        client.headers["Authorization"] = f"Bearer {settings.token()}"
        assert client.post("/api/goals", content="x" * 256001).status_code == 413
        with client.websocket_connect(
            "ws://127.0.0.1:8765/api/live", headers={"Origin": "http://127.0.0.1:8765"}
        ) as socket:
            socket.send_json({"token": settings.token(), "after": 0})
            assert socket.receive_json()["kind"] == "RUNTIME_STATE"


async def test_idle_websocket_disconnect_releases_subscription(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", workspace=tmp_path / "work")
    app = create_app(settings)
    runtime = app.state.runtime
    incoming, outgoing = asyncio.Queue(), asyncio.Queue()
    scope = {
        "type": "websocket",
        "asgi": {"version": "3.0", "spec_version": "2.4"},
        "scheme": "ws",
        "path": "/api/live",
        "raw_path": b"/api/live",
        "root_path": "",
        "query_string": b"",
        "headers": [(b"host", b"127.0.0.1:8765"), (b"origin", b"http://127.0.0.1:8765")],
        "client": ("127.0.0.1", 12345),
        "server": ("127.0.0.1", 8765),
        "subprotocols": [],
    }
    await runtime.start()
    connection = asyncio.create_task(app(scope, incoming.get, outgoing.put))
    try:
        await incoming.put({"type": "websocket.connect"})
        assert (await asyncio.wait_for(outgoing.get(), 1))["type"] == "websocket.accept"
        await incoming.put(
            {"type": "websocket.receive", "text": json.dumps({"token": settings.token()})}
        )
        assert (await asyncio.wait_for(outgoing.get(), 1))["type"] == "websocket.send"
        assert len(runtime.bus.subscribers) == 1
        await incoming.put({"type": "websocket.disconnect", "code": 1000})
        await asyncio.wait_for(connection, 1)
        assert not runtime.bus.subscribers
    finally:
        connection.cancel()
        await asyncio.gather(connection, return_exceptions=True)
        await runtime.close()
