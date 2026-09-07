from __future__ import annotations

import json
from pathlib import Path

from .types import Skill


class SkillRouter:
    """Two-stage router: inexpensive lexical recall followed by boundary-aware ranking."""

    def __init__(self, directory: Path) -> None:
        self.skills = [Skill(**item) for item in json.loads(directory.read_text())]

    def route(self, task: str, intent: str, limit: int = 3) -> list[Skill]:
        terms = set((task + " " + intent).lower().replace("_", " ").split())
        # Stage 1: recall candidates by declared task intent/tags.
        candidates = [
            skill for skill in self.skills
            if terms.intersection(x.lower() for x in skill.intents + skill.tags)
            or intent.lower() in (x.lower() for x in skill.intents)
        ]
        candidates = candidates or self.skills

        # Stage 2: favor semantic overlap, quality, and lower expected context cost.
        def score(skill: Skill) -> float:
            metadata = set(" ".join(skill.intents + skill.tags + skill.boundaries).lower().split())
            overlap = len(terms & metadata)
            return overlap * 10 + skill.success_rate * 5 - skill.expected_tokens / 10_000

        return sorted(candidates, key=score, reverse=True)[:limit]
