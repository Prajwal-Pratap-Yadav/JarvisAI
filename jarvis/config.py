"""Configuration is local; provider credentials are read only from the environment."""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


def default_data_dir() -> Path:
    base = os.getenv("LOCALAPPDATA") if os.name == "nt" else os.getenv("XDG_DATA_HOME")
    return Path(base or Path.home() / ".local" / "share") / "JarvisAI"


class Settings(BaseModel):
    data_dir: Path = Field(default_factory=default_data_dir)
    workspace: Path = Field(default_factory=lambda: Path.home() / "JarvisWorkspace")
    provider: Literal["offline", "ollama", "compatible"] = "offline"
    model: str = Field(default="phi3:mini", max_length=150)
    model_url: str = "http://127.0.0.1:11434"
    embedding_model: str = ""
    port: int = Field(default=8765, ge=1024, le=65535)
    concurrency: int = Field(default=4, ge=1, le=8)
    max_nodes: int = Field(default=24, ge=1, le=64)
    network_hosts: list[str] = Field(
        default_factory=lambda: ["docs.python.org", "en.wikipedia.org"]
    )
    desktop_enabled: bool = False
    proactive: bool = False
    setup_complete: bool = False
    history_days: int = Field(default=30, ge=1, le=365)

    @field_validator("model_url")
    @classmethod
    def validate_model_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Model URL cannot contain credentials, queries, or fragments")
        if parsed.scheme != "https" and not (
            parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            raise ValueError("Use HTTPS for remote providers, or HTTP on loopback")
        if not parsed.hostname:
            raise ValueError("Model URL must include a host")
        return value.rstrip("/")

    @field_validator("network_hosts")
    @classmethod
    def validate_hosts(cls, hosts: list[str]) -> list[str]:
        import re

        if len(hosts) > 100 or any(not re.fullmatch(r"[a-zA-Z0-9.-]+", h) for h in hosts):
            raise ValueError("Use exact DNS hostnames, without wildcards, ports, or paths")
        return sorted({h.lower().rstrip(".") for h in hosts})

    @classmethod
    def load(cls, data_dir: Path | None = None) -> Settings:
        directory = (
            data_dir or Path(os.getenv("JARVIS_DATA_DIR", str(default_data_dir())))
        ).resolve()
        path = directory / "settings.json"
        values = json.loads(path.read_text()) if path.exists() else {}
        values["data_dir"] = directory
        mappings = {
            "workspace": "WORKSPACE",
            "provider": "PROVIDER",
            "model": "MODEL",
            "model_url": "MODEL_URL",
            "port": "PORT",
            "desktop_enabled": "DESKTOP_ENABLED",
            "proactive": "PROACTIVE",
        }
        for key, env in mappings.items():
            if os.getenv(f"JARVIS_{env}"):
                values[key] = os.environ[f"JARVIS_{env}"]
        if os.getenv("JARVIS_NETWORK_HOSTS") is not None:
            values["network_hosts"] = [
                h.strip() for h in os.environ["JARVIS_NETWORK_HOSTS"].split(",") if h.strip()
            ]
        result = cls(**values)
        result.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        result.workspace = result.workspace.expanduser().resolve()
        result.workspace.mkdir(parents=True, exist_ok=True)
        return result

    def save(self) -> None:
        path = self.data_dir / "settings.json"
        temp = path.with_suffix(".tmp")
        temp.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        temp.chmod(0o600)
        temp.replace(path)

    def token(self) -> str:
        path = self.data_dir / "access.token"
        if not path.exists():
            try:
                with path.open("x", encoding="utf-8") as handle:
                    path.chmod(0o600)
                    handle.write(secrets.token_urlsafe(32))
            except FileExistsError:
                pass
        return path.read_text().strip()
