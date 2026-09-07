from __future__ import annotations

from typing import Protocol

from .types import ExecutionPlan, PlanStep, Skill


class Planner(Protocol):
    """规划器协议，可由 LLM、规则引擎或人工审批器实现。"""

    def build(self, task: str, intent: str, skills: list[Skill]) -> ExecutionPlan:
        """根据任务和已选 Skill 返回可审计的执行 DAG。"""


class HeuristicPlanner:
    """零依赖规划器：为本地 MVP 提供可预测、可测试的默认计划。"""

    def build(self, task: str, intent: str, skills: list[Skill]) -> ExecutionPlan:
        workers = list(dict.fromkeys(worker for skill in skills for worker in skill.workers))
        steps: list[PlanStep] = []

        # Coding 类任务先调研，再实施，最后验证；其他任务只执行 Skill 声明的 Worker。
        if intent == "implement":
            ordered = [worker for worker in ("research", "code", "test") if worker in workers]
        else:
            ordered = workers

        previous: str | None = None
        for index, worker in enumerate(ordered, 1):
            step_id = f"step-{index}-{worker}"
            steps.append(PlanStep(step_id=step_id, worker=worker, depends_on=[previous] if previous else []))
            previous = step_id
        return ExecutionPlan(goal=task, steps=steps)
