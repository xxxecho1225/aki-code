from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .types import AgentResult, MemoryItem


class MemoryStore:
    """追加式本地记忆存储，便于审计；生产环境可替换为向量库和 SQL 索引。"""

    def __init__(self, path: Path) -> None:
        self.path = path

    def consolidate(self, task: str, results: list[AgentResult]) -> None:
        # 只沉淀结构化事实、风险和结果，不保存完整上下文，降低隐私和 Token 成本。
        entry = {
            "task": task,
            "facts": [item for result in results for item in result.evidence],
            "lessons": [risk for result in results for risk in result.risks],
            "results": [asdict(result) for result in results],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # JSONL 便于增量写入、按行检索和后续离线重建索引。
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def recall(self, query: str, limit: int = 3) -> list[MemoryItem]:
        """按词项重叠召回历史经验；结果始终是参考信息而非系统指令。"""
        if not self.path.exists():
            return []
        terms = set(query.lower().split())
        candidates: list[MemoryItem] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                raw = json.loads(line)
                item = MemoryItem(raw["task"], raw.get("facts", []), raw.get("lessons", []))
            except (json.JSONDecodeError, KeyError, TypeError):
                # 单条旧数据损坏时跳过，不阻塞新的任务执行。
                continue
            haystack = " ".join([item.task, *item.facts, *item.lessons]).lower()
            item.score = float(sum(term in haystack for term in terms))
            if item.score:
                candidates.append(item)
        return sorted(candidates, key=lambda item: item.score, reverse=True)[:limit]
