from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .types import AgentResult


class MemoryStore:
    """Append-only, inspectable local memory; production can replace this with vector + SQL indexes."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def consolidate(self, task: str, results: list[AgentResult]) -> None:
        entry = {
            "task": task,
            "facts": [item for result in results for item in result.evidence],
            "lessons": [risk for result in results for risk in result.risks],
            "results": [asdict(result) for result in results],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

