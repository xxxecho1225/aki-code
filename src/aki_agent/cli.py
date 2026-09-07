from __future__ import annotations

import argparse
from pathlib import Path

from .orchestrator import Orchestrator


def main() -> None:
    # 命令行只负责收集最小输入；任务规划与权限判断全部留在运行时内部。
    parser = argparse.ArgumentParser(description="Run the Aki Agent centralized coding loop.")
    parser.add_argument("task")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--approve-writes", action="store_true")
    args = parser.parse_args()
    agent = Orchestrator(Path(args.workspace), args.approve_writes)
    print(agent.render(agent.run(args.task)))


if __name__ == "__main__":
    main()
