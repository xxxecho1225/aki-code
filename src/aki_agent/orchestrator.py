from __future__ import annotations

from pathlib import Path

from .memory import MemoryStore
from .policy import PolicyGateway
from .skills import SkillRouter
from .tools import ArtifactStore, ToolRegistry
from .types import AgentResult, RunState
from .workers import WORKERS


class Orchestrator:
    """Central control plane. Workers never delegate or retain global state."""

    def __init__(self, workspace: Path, approve_writes: bool = False) -> None:
        self.workspace = workspace.resolve()
        root = Path(__file__).resolve().parents[2]
        self.router = SkillRouter(root / "skills" / "catalog.json")
        policy = PolicyGateway(self.workspace, approve_writes)
        self.tools = ToolRegistry(self.workspace, policy, ArtifactStore(self.workspace / ".aki" / "artifacts"))
        self.memory = MemoryStore(self.workspace / ".aki" / "memory.jsonl")

    @staticmethod
    def infer_intent(task: str) -> str:
        lowered = task.lower()
        if any(word in lowered for word in ("test", "verify", "review", "检查", "测试")):
            return "verify"
        if any(word in lowered for word in ("implement", "fix", "add", "修改", "实现", "修复")):
            return "implement"
        return "inspect"

    def run(self, task: str) -> RunState:
        state = RunState(task=task, intent=self.infer_intent(task))
        state.selected_skills = self.router.route(task, state.intent)
        worker_names = dict.fromkeys(name for skill in state.selected_skills for name in skill.workers)
        for name in worker_names:
            result: AgentResult = WORKERS[name](self.tools).run(task, state.selected_skills)
            state.results.append(result)
        self.memory.consolidate(task, state.results)
        return state

    def render(self, state: RunState) -> str:
        skills = ", ".join(skill.name for skill in state.selected_skills)
        lines = [f"Intent: {state.intent}", f"Selected skills: {skills}"]
        lines.extend(f"[{result.worker}/{result.status}] {result.summary}" for result in state.results)
        return "\n".join(lines)
