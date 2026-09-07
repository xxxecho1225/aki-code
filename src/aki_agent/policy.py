from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .types import Risk, ToolCall


@dataclass
class PolicyDecision:
    allowed: bool
    risk: Risk
    reason: str
    needs_confirmation: bool = False


class PolicyGateway:
    """The sole authorization point for every tool invocation."""

    SAFE_COMMANDS = ("pytest", "python -m unittest", "ruff check", "git diff", "git status")
    INJECTION_MARKERS = ("ignore previous instructions", "system prompt", "override policy")

    def __init__(self, workspace: Path, approve_writes: bool = False) -> None:
        self.workspace = workspace.resolve()
        self.approve_writes = approve_writes

    def authorize(self, call: ToolCall) -> PolicyDecision:
        if any(marker in str(call.arguments).lower() for marker in self.INJECTION_MARKERS):
            return PolicyDecision(False, Risk.DENY, "Possible prompt-injection content in tool arguments")

        if call.name in {"read_file", "list_files", "search_text"}:
            return self._check_path(call, Risk.LOW)
        if call.name == "write_file":
            result = self._check_path(call, Risk.MEDIUM)
            if result.allowed and not self.approve_writes:
                return PolicyDecision(False, Risk.MEDIUM, "Write requires explicit --approve-writes", True)
            return result
        if call.name == "run_command":
            command = call.arguments.get("command", "")
            shell_operators = (";", "&&", "||", "|", "$", "`", ">", "<", "\n")
            if any(operator in command for operator in shell_operators) or not command.startswith(self.SAFE_COMMANDS):
                return PolicyDecision(False, Risk.HIGH, "Command is outside allowlist", True)
            return PolicyDecision(True, Risk.MEDIUM, "Approved command allowlist")
        return PolicyDecision(False, Risk.DENY, f"Unknown tool: {call.name}")

    def _check_path(self, call: ToolCall, risk: Risk) -> PolicyDecision:
        raw = call.arguments.get("path", ".")
        path = (self.workspace / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
        try:
            path.relative_to(self.workspace)
        except ValueError:
            return PolicyDecision(False, Risk.DENY, "Path escapes workspace")
        return PolicyDecision(True, risk, "Path is inside workspace")
