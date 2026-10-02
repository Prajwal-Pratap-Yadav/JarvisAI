"""Provider-neutral text, image, and embedding interfaces with bounded requests."""

from __future__ import annotations

import json
import os
from typing import Any, Protocol

import httpx

from jarvis.config import Settings
from jarvis.security import Unavailable


class LanguageModel(Protocol):
    async def chat(self, messages: list[dict], *, json_mode: bool = False) -> str: ...
    async def embed(self, text: str) -> list[float]: ...


class ModelGateway:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(90, connect=5), trust_env=False)

    async def chat(self, messages: list[dict], *, json_mode: bool = False) -> str:
        s = self.settings
        if s.provider == "offline":
            raise Unavailable(
                "No language model configured. System, files, memory, and task graphs work offline. Select Ollama or a compatible provider in Settings for conversation and AI planning."
            )
        headers = {}
        payload: dict[str, Any] = {"model": s.model, "messages": messages, "stream": False}
        if s.provider == "ollama":
            url = f"{s.model_url}/api/chat"
            payload["options"] = {"temperature": 0.2, "num_predict": 2048}
            if json_mode:
                payload["format"] = "json"
        else:
            url = f"{s.model_url}/chat/completions"
            if os.getenv("JARVIS_API_KEY"):
                headers["Authorization"] = f"Bearer {os.environ['JARVIS_API_KEY']}"
            payload["max_tokens"] = 2048
            if json_mode:
                payload["response_format"] = {"type": "json_object"}
            # Translate the normalized image representation at the provider boundary.
            payload["messages"] = []
            for message in messages:
                if message.get("images"):
                    content = [{"type": "text", "text": message["content"]}]
                    content.extend(
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}}
                        for img in message["images"]
                    )
                    payload["messages"].append({"role": message["role"], "content": content})
                else:
                    payload["messages"].append(message)
        result = await self.client.post(url, json=payload, headers=headers)
        result.raise_for_status()
        data = result.json()
        text = (
            data["message"]["content"]
            if s.provider == "ollama"
            else data["choices"][0]["message"]["content"]
        )
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Provider returned an empty response")
        return text[:64000]

    async def embed(self, text: str) -> list[float]:
        s = self.settings
        if not s.embedding_model or s.provider == "offline":
            raise Unavailable("No embedding model configured")
        headers = (
            {"Authorization": f"Bearer {os.environ['JARVIS_API_KEY']}"}
            if os.getenv("JARVIS_API_KEY")
            else {}
        )
        endpoint = "/api/embed" if s.provider == "ollama" else "/embeddings"
        response = await self.client.post(
            s.model_url + endpoint,
            headers=headers,
            json={"model": s.embedding_model, "input": text[:16000]},
        )
        response.raise_for_status()
        data = response.json()
        return data["embeddings"][0] if s.provider == "ollama" else data["data"][0]["embedding"]

    async def health(self) -> dict:
        if self.settings.provider == "offline":
            return {"available": False, "detail": "Offline tools ready; no language model selected"}
        path = "/api/tags" if self.settings.provider == "ollama" else "/models"
        headers = (
            {"Authorization": f"Bearer {os.environ['JARVIS_API_KEY']}"}
            if os.getenv("JARVIS_API_KEY")
            else {}
        )
        try:
            response = await self.client.get(
                self.settings.model_url + path, headers=headers, timeout=5
            )
            response.raise_for_status()
            data = response.json()
            available = [
                m.get("name", m.get("id")) for m in data.get("models", data.get("data", []))
            ]
            present = self.settings.model in available
            return {
                "available": present,
                "models": available,
                "detail": "Selected model found"
                if present
                else "Endpoint reachable; selected model not listed",
            }
        except (httpx.HTTPError, ValueError, KeyError):
            return {
                "available": False,
                "detail": "Model endpoint unreachable or rejected credentials",
            }

    async def close(self) -> None:
        await self.client.aclose()


def parse_json(text: str) -> dict:
    """Accept JSON and a single JSON fence, never evaluate provider-generated code."""
    text = text.strip()
    if text.startswith("```json") and text.endswith("```"):
        text = text[7:-3].strip()
    result = json.loads(text)
    if not isinstance(result, dict):
        raise ValueError("Expected a JSON object")
    return result
