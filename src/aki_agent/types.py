from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class Risk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    DENY = "deny"


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    caller: str = "orchestrator"
    reason: str = ""


@dataclass
class ToolResult:
    ok: bool
    content: str
    artifact_id: str | None = None
    error: str | None = None


@dataclass
class Skill:
    name: str
    description: str
    intents: list[str]
    tags: list[str]
    tools: list[str]
    workers: list[str]
    boundaries: list[str] = field(default_factory=list)
    expected_tokens: int = 1000
    success_rate: float = 0.7


@dataclass
class AgentResult:
    worker: str
    status: Literal["success", "partial", "failed"]
    summary: str
    evidence: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)


@dataclass
class RunState:
    task: str
    intent: str
    selected_skills: list[Skill] = field(default_factory=list)
    results: list[AgentResult] = field(default_factory=list)
    tool_trace: list[ToolCall] = field(default_factory=list)
