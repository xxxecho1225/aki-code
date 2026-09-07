from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .policy import PolicyGateway
from .types import ToolCall, ToolResult


@dataclass
class ArtifactStore:
    root: Path
    _counter: int = 0

    def put(self, text: str) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        self._counter += 1
        artifact_id = f"artifact-{self._counter:04d}.txt"
        (self.root / artifact_id).write_text(text)
        return artifact_id


@dataclass
class ToolRegistry:
    workspace: Path
    policy: PolicyGateway
    artifacts: ArtifactStore
    audit: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.workspace = self.workspace.resolve()

    def schemas(self) -> list[dict]:
        return [
            {"name": "list_files", "description": "List workspace files", "parameters": {"path": "string"}},
            {"name": "read_file", "description": "Read a UTF-8 text file", "parameters": {"path": "string"}},
            {"name": "search_text", "description": "Search text in workspace", "parameters": {"query": "string"}},
            {"name": "write_file", "description": "Write a UTF-8 file in workspace", "parameters": {"path": "string", "content": "string"}},
            {"name": "run_command", "description": "Run an allowlisted verification command", "parameters": {"command": "string"}},
        ]

    def invoke(self, call: ToolCall) -> ToolResult:
        decision = self.policy.authorize(call)
        self.audit.append({"tool": call.name, "arguments": call.arguments, "allowed": decision.allowed, "reason": decision.reason})
        if not decision.allowed:
            return ToolResult(False, "", error=decision.reason)
        handler: Callable[[dict], str] = getattr(self, f"_{call.name}")
        try:
            output = handler(call.arguments)
            artifact_id = self.artifacts.put(output) if len(output) > 1_500 else None
            preview = output[:1_500] + ("\n[externalized; see artifact]" if artifact_id else "")
            return ToolResult(True, preview, artifact_id=artifact_id)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            return ToolResult(False, "", error=str(exc))

    def _path(self, value: str) -> Path:
        return (self.workspace / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()

    def _list_files(self, args: dict) -> str:
        root = self._path(args.get("path", "."))
        return "\n".join(str(path.relative_to(self.workspace)) for path in root.rglob("*") if path.is_file())

    def _read_file(self, args: dict) -> str:
        return self._path(args["path"]).read_text(encoding="utf-8")

    def _search_text(self, args: dict) -> str:
        query = args["query"].lower()
        hits = []
        for path in self.workspace.rglob("*"):
            if path.is_file() and ".git" not in path.parts:
                try:
                    for number, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
                        if query in line.lower():
                            hits.append(f"{path.relative_to(self.workspace)}:{number}: {line[:240]}")
                except OSError:
                    continue
        return "\n".join(hits[:200]) or "No matches."

    def _write_file(self, args: dict) -> str:
        path = self._path(args["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(args["content"], encoding="utf-8")
        return f"Wrote {path.relative_to(self.workspace)}"

    def _run_command(self, args: dict) -> str:
        completed = subprocess.run(shlex.split(args["command"]), cwd=self.workspace, text=True, capture_output=True, timeout=60)
        if completed.returncode:
            raise subprocess.CalledProcessError(completed.returncode, args["command"], output=completed.stdout, stderr=completed.stderr)
        return (completed.stdout + completed.stderr).strip() or f"Command exited {completed.returncode}"
