# Aki Agent

一个面向 Coding 场景的中心化多 Agent MVP。主 Agent 保持规划、审批和最终交付控制权；Worker 只通过受限 Tool Use 执行任务。

## 当前能力

- Skill Directory：JSON 元数据目录，按意图/标签粗召回，再按边界、成本和历史质量精排。
- Tool Use：所有工具调用都经由 `ToolRegistry -> PolicyGateway -> AuditLog`。
- 安全：路径白名单、读写分级、命令白名单、外部内容不可信标记、人工确认钩子。
- 多 Agent：Research、Code、Test Worker 的最小结果回传；主 Agent 负责 DAG 和汇总。
- 记忆与上下文：结构化执行记忆、外置 Artifact、稳定引用及摘要。

## 运行

```bash
python -m aki_agent "检查当前项目结构并给出实施建议" --workspace .
python -m aki_agent "搜索 TODO" --workspace .
python -m unittest discover -s tests -v
```

`--approve-writes` 允许受限工作区内的 `write_file`；命令执行仍只允许配置的白名单前缀。

## 接入真实模型

`orchestrator.py` 中的 `Planner` 是协议。将当前 `HeuristicPlanner` 换成任意支持 function/tool calling 的客户端即可：把模型产生的 `ToolCall` 交给 `ToolRegistry.invoke()`，并将 `ToolResult` 回填给模型，直到模型给出最终答案。模型不得绕开 Registry 直接访问 shell、文件或网络。

