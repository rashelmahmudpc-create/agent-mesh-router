"""কনফিগ পড়া — `config/agents.json` থেকেই পুরো টিমের তালিকা আসে।"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "agents.json"


@dataclass
class AgentSpec:
    name: str
    label: str = ""
    kind: str = "cli"  # cli | github_issue
    enabled: bool = True
    roles: list[str] = field(default_factory=lambda: ["worker", "chat"])
    command: list[str] = field(default_factory=list)
    fallback_commands: list[list[str]] = field(default_factory=list)
    timeout_sec: int = 900
    env: dict[str, str] = field(default_factory=dict)
    keys: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    daily_limit: int | None = None
    mention: str = ""
    notes: str = ""

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def display(self) -> str:
        return self.label or self.name

    @classmethod
    def from_dict(cls, data: dict) -> "AgentSpec":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class Settings:
    default_agent: str = "opencode"
    max_rounds: int = 3
    max_calls_per_run: int = 8
    max_pair_calls: int = 3
    reply_char_limit: int = 4000


@dataclass
class MeshConfig:
    settings: Settings
    agents: list[AgentSpec]

    def get(self, name: str) -> AgentSpec | None:
        name = (name or "").lower()
        for agent in self.agents:
            if agent.name.lower() == name:
                return agent
        return None

    def enabled(self) -> list[AgentSpec]:
        return [a for a in self.agents if a.enabled]

    def chat_agents(self) -> list[AgentSpec]:
        return [a for a in self.enabled() if a.has_role("chat")]

    def names(self) -> list[str]:
        return [a.name.lower() for a in self.enabled()]

    @classmethod
    def load(cls, path: str | Path | None = None) -> "MeshConfig":
        path = Path(path or os.environ.get("MESH_CONFIG") or DEFAULT_CONFIG)
        data = json.loads(path.read_text(encoding="utf-8"))
        settings = Settings(**{k: v for k, v in data.get("settings", {}).items() if k in Settings.__dataclass_fields__})  # type: ignore[attr-defined]
        agents = [AgentSpec.from_dict(item) for item in data.get("agents", [])]
        return cls(settings=settings, agents=agents)
