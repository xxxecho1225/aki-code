from __future__ import annotations

from pathlib import Path

from .context import ContextManager, PromptContext
from .memory import MemoryStore
from .planning import HeuristicPlanner, Planner
from .policy import PolicyGateway
from .skills import SkillRouter
from .tools import ArtifactStore, ToolRegistry
from .types import AgentResult, RunState, ToolCall, ToolResult
from .workers import WORKERS


class Orchestrator:
    """中心化控制平面：Worker 不得继续委派任务，也不持有全局状态。"""

    def __init__(self, workspace: Path, approve_writes: bool = False, planner: Planner | None = None) -> None:
        self.workspace = workspace.resolve()
        # Skill 目录随代码发布，工作区仅保存用户项目和运行时数据。
        root = Path(__file__).resolve().parents[2]
        self.router = SkillRouter(root / "skills" / "catalog.json")
        policy = PolicyGateway(self.workspace, approve_writes)
        self.tools = ToolRegistry(self.workspace, policy, ArtifactStore(self.workspace / ".aki" / "artifacts"))
        self.memory = MemoryStore(self.workspace / ".aki" / "memory.jsonl")
        self.planner = planner or HeuristicPlanner()
        self.context = ContextManager()

    @staticmethod
    def infer_intent(task: str) -> str:
        """MVP 的轻量意图识别；接入模型后可替换为分类器或结构化规划结果。"""
        lowered = task.lower()
        if any(word in lowered for word in ("test", "verify", "review", "检查", "测试")):
            return "verify"
        if any(word in lowered for word in ("implement", "fix", "add", "修改", "实现", "修复")):
            return "implement"
        return "inspect"

    def run(self, task: str) -> RunState:
        state = RunState(task=task, intent=self.infer_intent(task))
        state.selected_skills = self.router.route(task, state.intent)
        # 先按需召回记忆，再由规划器生成 DAG；记忆仅作为规划参考，不能覆盖策略。
        state.recalled_memory = self.memory.recall(task)
        state.plan = self.planner.build(task, state.intent, state.selected_skills)
        self._run_plan(state)
        # 无论成功或部分失败都沉淀结果，避免重复踩到已知风险。
        self.memory.consolidate(task, state.results)
        return state

    def _run_plan(self, state: RunState) -> None:
        """按依赖顺序执行计划；失败节点会阻断其后继节点。"""
        assert state.plan is not None
        by_id = {step.step_id: step for step in state.plan.steps}
        for step in state.plan.steps:
            dependencies = [by_id[dependency] for dependency in step.depends_on]
            if any(dependency.status in {"failed", "skipped"} for dependency in dependencies):
                step.status = "skipped"
                state.results.append(AgentResult(step.worker, "partial", "Skipped because a dependency failed."))
                continue
            worker_type = WORKERS.get(step.worker)
            if worker_type is None:
                step.status = "failed"
                state.results.append(AgentResult(step.worker, "failed", "Worker is not registered."))
                continue
            step.status = "running"
            result: AgentResult = worker_type(self.tools).run(state.task, state.selected_skills)
            state.results.append(result)
            step.status = result.status

    def execute_tool_calls(self, state: RunState, calls: list[ToolCall]) -> list[ToolResult]:
        """供模型 Function Calling 循环使用的受控执行接口。

        模型只生成 ToolCall；主 Agent 在此处记录轨迹、限制 Skill 范围并交给
        PolicyGateway 审批，任何模型都不拥有绕过该链路的直接工具权限。
        """
        allowed_tools = {tool for skill in state.selected_skills for tool in skill.tools}
        results = []
        for call in calls:
            state.tool_trace.append(call)
            results.append(self.tools.invoke(call, allowed_tools))
        return results

    def build_context(self, state: RunState) -> PromptContext:
        """为下一次模型推理生成可缓存的分层上下文快照。"""
        return self.context.build(state)

    def render(self, state: RunState) -> str:
        skills = ", ".join(skill.name for skill in state.selected_skills)
        lines = [f"Intent: {state.intent}", f"Selected skills: {skills}"]
        if state.plan:
            lines.append("Plan: " + ", ".join(f"{step.worker}={step.status}" for step in state.plan.steps))
        lines.extend(f"[{result.worker}/{result.status}] {result.summary}" for result in state.results)
        return "\n".join(lines)
