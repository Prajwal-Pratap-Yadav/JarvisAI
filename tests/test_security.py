import socket
import time

import pytest

from jarvis.network import Web
from jarvis.security import ApprovalGate, Denied, PathPolicy, redact


@pytest.mark.parametrize(
    "name",
    [
        "../escape",
        "/tmp/absolute",
        ".env",
        ".env.local",
        ".git/config",
        ".ssh/id_rsa",
        "nul\x00name",
    ],
)
def test_confined_paths(tmp_path, name):
    with pytest.raises(Denied):
        PathPolicy(tmp_path).resolve(name)


def test_symlink_escape(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    try:
        (root / "link").symlink_to(tmp_path, target_is_directory=True)
    except OSError:
        pytest.skip("OS does not permit symlinks")
    with pytest.raises(Denied):
        PathPolicy(root).resolve("link/out")


def test_exact_grants_and_expiry():
    gate = ApprovalGate()
    a = gate.request("r", "n", "write", {"content": "one"})
    gate.decide(a.id, True)
    assert not gate.consume("r", "n", "write", {"content": "two"})
    a = gate.request("r", "n", "write", {"content": "one"})
    a.expires = time.time() - 1
    with pytest.raises(Denied):
        gate.decide(a.id, True)


def test_redaction():
    data = redact({"api_key": "private", "text": "password=hunter2 token=secret-value"})
    assert "hunter2" not in str(data) and "private" not in str(data)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "https://u:p@example.com",
        "https://example.com:444",
        "file:///etc/passwd",
        "https://other.example",
    ],
)
def test_url_policy(url):
    with pytest.raises(Denied):
        Web(["example.com"]).validate(url)


@pytest.mark.parametrize(
    "addresses",
    [["127.0.0.1"], ["169.254.169.254"], ["::1"], ["10.1.2.3"], ["93.184.216.34", "127.0.0.1"]],
)
def test_private_and_mixed_dns_blocked(monkeypatch, addresses):
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", (ip, 443)) for ip in addresses]
    )
    with pytest.raises(Denied):
        Web(["example.com"]).validate("https://example.com")


def test_dns_pin_target(monkeypatch):
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("93.184.216.34", 443))]
    )
    assert Web(["example.com"]).validate("https://example.com/docs?q=1") == (
        "example.com",
        "93.184.216.34",
        "/docs?q=1",
    )


async def test_hash_checked_write_and_readback(runtime):
    tools = runtime.tools
    first = await tools.files_write({"path": "a.txt", "content": "first", "expected_sha256": None})
    with pytest.raises(Denied):
        await tools.files_write({"path": "a.txt", "content": "second", "expected_sha256": None})
    second = await tools.files_write(
        {"path": "a.txt", "content": "second", "expected_sha256": first["sha256"]}
    )
    assert second["verified"] and (await tools.files_read({"path": "a.txt"}))["content"] == "second"
    with pytest.raises(Denied):
        await tools.files_write(
            {"path": "a.txt", "content": "stale", "expected_sha256": first["sha256"]}
        )


async def test_credential_write_rejected(runtime):
    with pytest.raises(Denied):
        await runtime.tools.files_write(
            {"path": "secret.txt", "content": "api_key=privatevalue", "expected_sha256": None}
        )
