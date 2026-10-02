"""Typed tools and capability discovery shared by the planner, policy, and HUD."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel

Risk = Literal["low", "medium", "high"]


@dataclass
class Tool:
    name: str
    description: str
    category: str
    agent: str
    inputs: type[BaseModel]
    handler: Callable[[dict], Awaitable[dict]]
    risk: Risk = "low"
    confirmation: bool = False
    timeout: float = 30
    retries: int = 0
    idempotent: bool = True
    required_outputs: tuple[str, ...] = ()
    available: Callable[[], tuple[bool, str]] = lambda: (True, "Ready")

    def metadata(self) -> dict[str, Any]:
        ready, detail = self.available()
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "agent": self.agent,
            "input_schema": self.inputs.model_json_schema(),
            "output_schema": {"type": "object", "required": list(self.required_outputs)},
            "risk": self.risk,
            "confirmation": self.confirmation or self.risk != "low",
            "permissions": ["workspace"]
            if self.category in {"FILE", "CODE", "GIT"}
            else [self.category.lower()],
            "timeout": self.timeout,
            "retry_policy": {"max_retries": self.retries if self.idempotent else 0},
            "audit": "durable tool start, result summary, validation, duration",
            "available": ready,
            "availability_detail": detail,
        }


class Registry:
    def __init__(self) -> None:
        self.tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self.tools:
            raise ValueError(f"Duplicate tool: {tool.name}")
        self.tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self.tools:
            raise ValueError(f"Unknown capability: {name}")
        return self.tools[name]

    def catalog(self) -> list[dict]:
        return [tool.metadata() for tool in self.tools.values()]

    def graph(self) -> dict:
        nodes: dict[str, dict] = {}
        edges = []
        for tool in self.catalog():
            agent_id = f"agent:{tool['agent']}"
            nodes[agent_id] = {"id": agent_id, "kind": "agent", "label": tool["agent"]}
            nodes[tool["name"]] = {
                "id": tool["name"],
                "kind": "tool",
                "label": tool["name"],
                "available": tool["available"],
            }
            edges.append({"from": agent_id, "to": tool["name"]})
        return {"nodes": list(nodes.values()), "edges": edges}
