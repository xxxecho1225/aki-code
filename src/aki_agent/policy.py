from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shlex

from .types import Risk, ToolCall


@dataclass
class PolicyDecision:
    allowed: bool
    risk: Risk
    reason: str
    needs_confirmation: bool = False


class PolicyGateway:
    """所有 Tool Use 的唯一授权点，禁止 Agent 直接执行外部操作。"""

    # 以 token 前缀表示允许的命令，不能只做字符串 startswith 判断。
    SAFE_COMMANDS = (
        ("pytest",),
        ("python", "-m", "unittest"),
        ("python3", "-m", "unittest"),
        ("ruff", "check"),
        ("git", "diff"),
        ("git", "status"),
    )
    INJECTION_MARKERS = ("ignore previous instructions", "system prompt", "override policy")

    def __init__(self, workspace: Path, approve_writes: bool = False) -> None:
        self.workspace = workspace.resolve()
        self.approve_writes = approve_writes

    def authorize(self, call: ToolCall) -> PolicyDecision:
        # 外部文本可能携带注入指令；命中标记时直接拒绝，不将其当作执行依据。
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
            try:
                tokens = tuple(shlex.split(command))
            except ValueError:
                return PolicyDecision(False, Risk.HIGH, "Malformed command", True)
            is_allowed = any(tokens[: len(prefix)] == prefix for prefix in self.SAFE_COMMANDS)
            if any(operator in command for operator in shell_operators) or not is_allowed:
                return PolicyDecision(False, Risk.HIGH, "Command is outside allowlist", True)
            return PolicyDecision(True, Risk.MEDIUM, "Approved command allowlist")
        return PolicyDecision(False, Risk.DENY, f"Unknown tool: {call.name}")

    def _check_path(self, call: ToolCall, risk: Risk) -> PolicyDecision:
        # resolve 后再判定归属，可拦截 ../ 和符号链接导致的工作区逃逸。
        raw = call.arguments.get("path", ".")
        path = (self.workspace / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
        try:
            path.relative_to(self.workspace)
        except ValueError:
            return PolicyDecision(False, Risk.DENY, "Path escapes workspace")
        return PolicyDecision(True, risk, "Path is inside workspace")
