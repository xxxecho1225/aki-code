from __future__ import annotations

import json
from pathlib import Path

from .types import Skill


class SkillRouter:
    """两阶段 Skill 路由：低成本粗召回，再依据边界和质量精排。"""

    def __init__(self, directory: Path) -> None:
        # Skill 采用数据驱动配置，新增能力时无需修改调度器代码。
        self.skills = [Skill(**item) for item in json.loads(directory.read_text())]

    def route(self, task: str, intent: str, limit: int = 3) -> list[Skill]:
        terms = set((task + " " + intent).lower().replace("_", " ").split())
        # 第一阶段：仅按意图和标签粗召回，避免全部 Skill 进入昂贵的精排。
        candidates = [
            skill for skill in self.skills
            if terms.intersection(x.lower() for x in skill.intents + skill.tags)
            or intent.lower() in (x.lower() for x in skill.intents)
        ]
        candidates = candidates or self.skills

        # 第二阶段：综合词项重合、历史成功率和预估上下文成本。
        def score(skill: Skill) -> float:
            metadata = set(" ".join(skill.intents + skill.tags + skill.boundaries).lower().split())
            overlap = len(terms & metadata)
            return overlap * 10 + skill.success_rate * 5 - skill.expected_tokens / 10_000

        ranked = sorted(candidates, key=score, reverse=True)[:limit]
        if intent == "implement":
            # 编码前默认保留只读调研能力，避免 Code Worker 在缺少仓库事实时直接修改。
            research = next((skill for skill in self.skills if skill.name == "repository-research"), None)
            if research and research.name not in {skill.name for skill in ranked}:
                ranked.insert(0, research)
        return ranked[:limit]
