from __future__ import annotations

from .tools import ToolRegistry
from .types import AgentResult, Skill, ToolCall


class Worker:
    name = "worker"

    def __init__(self, tools: ToolRegistry) -> None:
        self.tools = tools

    def run(self, task: str, skills: list[Skill]) -> AgentResult:
        raise NotImplementedError


class ResearchWorker(Worker):
    name = "research"

    def run(self, task: str, skills: list[Skill]) -> AgentResult:
        result = self.tools.invoke(ToolCall("list_files", {"path": "."}, self.name, "map repository"))
        files = result.content.splitlines()[:30] if result.ok else []
        query = "TODO" if "todo" in task.lower() else task.split()[0] if task.split() else ""
        matches = self.tools.invoke(ToolCall("search_text", {"query": query}, self.name, "find relevant evidence"))
        return AgentResult(self.name, "success", f"Inspected {len(files)} files; searched for '{query}'.", files[:8] + matches.content.splitlines()[:8])


class TestWorker(Worker):
    name = "test"

    def run(self, task: str, skills: list[Skill]) -> AgentResult:
        result = self.tools.invoke(ToolCall("run_command", {"command": "python -m unittest discover -s tests -v"}, self.name, "verify changes"))
        if result.ok:
            return AgentResult(self.name, "success", "Verification command completed.", [result.content])
        return AgentResult(self.name, "partial", "No verification executed.", risks=[result.error or "unknown error"])


class CodeWorker(Worker):
    name = "code"

    def run(self, task: str, skills: list[Skill]) -> AgentResult:
        # Deliberately does not invent edits. A model-backed planner supplies proposed write calls.
        return AgentResult(self.name, "partial", "Code worker is ready for model-supplied scoped ToolCalls.", risks=["No autonomous file mutation without an explicit proposed patch."])


WORKERS = {worker.name: worker for worker in (ResearchWorker, TestWorker, CodeWorker)}
