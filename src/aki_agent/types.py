from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class Risk(str, Enum):
    """策略层风险等级；DENY 表示无条件拒绝。"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    DENY = "deny"


@dataclass
class ToolCall:
    """模型或 Worker 提出的工具调用意图，尚未获得执行权限。"""
    name: str
    arguments: dict[str, Any]
    caller: str = "orchestrator"
    reason: str = ""


@dataclass
class ToolResult:
    """经策略审查后的工具执行结果；大结果由 artifact_id 指向外置工件。"""
    ok: bool
    content: str
    artifact_id: str | None = None
    error: str | None = None


@dataclass
class Skill:
    """可配置的能力单元，声明适用场景、可用工具和运行边界。"""
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
    """Worker 的最小结构化回传，避免将完整对话传回主 Agent。"""
    worker: str
    status: Literal["success", "partial", "failed"]
    summary: str
    evidence: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)


@dataclass
class PlanStep:
    """执行计划中的一个原子节点，由主 Agent 维护状态和依赖。"""
    step_id: str
    worker: str
    depends_on: list[str] = field(default_factory=list)
    status: Literal["pending", "running", "success", "partial", "failed", "skipped"] = "pending"


@dataclass
class ExecutionPlan:
    """任务 DAG 的轻量表示；当前实现不把控制权下放给子 Agent。"""
    goal: str
    steps: list[PlanStep] = field(default_factory=list)


@dataclass
class MemoryItem:
    """从长期记忆中召回的最小证据单元。"""
    task: str
    facts: list[str]
    lessons: list[str]
    score: float = 0.0


@dataclass
class RunState:
    """单次任务的可审计状态快照。"""
    task: str
    intent: str
    selected_skills: list[Skill] = field(default_factory=list)
    plan: ExecutionPlan | None = None
    recalled_memory: list[MemoryItem] = field(default_factory=list)
    results: list[AgentResult] = field(default_factory=list)
    tool_trace: list[ToolCall] = field(default_factory=list)
