from __future__ import annotations

from .tools import ToolRegistry
from .types import AgentResult, Skill, ToolCall


class Worker:
    """受主 Agent 调度的受限执行单元。"""
    name = "worker"

    def __init__(self, tools: ToolRegistry) -> None:
        self.tools = tools

    def run(self, task: str, skills: list[Skill]) -> AgentResult:
        raise NotImplementedError


class ResearchWorker(Worker):
    """只读调研 Worker：先获取文件概览，再搜索任务相关证据。"""
    name = "research"

    def run(self, task: str, skills: list[Skill]) -> AgentResult:
        # 即使 Worker 自己构造调用，也必须继承本次 Skill 的工具范围。
        allowed = {tool for skill in skills if self.name in skill.workers for tool in skill.tools}
        result = self.tools.invoke(ToolCall("list_files", {"path": "."}, self.name, "map repository"), allowed)
        files = result.content.splitlines()[:30] if result.ok else []
        query = "TODO" if "todo" in task.lower() else task.split()[0] if task.split() else ""
        matches = self.tools.invoke(ToolCall("search_text", {"query": query}, self.name, "find relevant evidence"), allowed)
        return AgentResult(self.name, "success", f"Inspected {len(files)} files; searched for '{query}'.", files[:8] + matches.content.splitlines()[:8])


class TestWorker(Worker):
    """验证 Worker：仅运行策略允许的测试命令，不修改源代码。"""
    name = "test"

    def run(self, task: str, skills: list[Skill]) -> AgentResult:
        allowed = {tool for skill in skills if self.name in skill.workers for tool in skill.tools}
        result = self.tools.invoke(ToolCall("run_command", {"command": "python3 -m unittest discover -s tests -v"}, self.name, "verify changes"), allowed)
        if result.ok:
            return AgentResult(self.name, "success", "Verification command completed.", [result.content])
        return AgentResult(self.name, "partial", "No verification executed.", risks=[result.error or "unknown error"])


class CodeWorker(Worker):
    """代码 Worker 的占位实现，等待模型提供经审查的精确修改计划。"""
    name = "code"

    def run(self, task: str, skills: list[Skill]) -> AgentResult:
        # 不自主猜测修改内容；必须由模型规划器提供明确的写入 ToolCall。
        return AgentResult(self.name, "partial", "Code worker is ready for model-supplied scoped ToolCalls.", risks=["No autonomous file mutation without an explicit proposed patch."])


WORKERS = {worker.name: worker for worker in (ResearchWorker, TestWorker, CodeWorker)}
