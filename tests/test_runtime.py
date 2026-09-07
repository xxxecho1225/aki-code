import tempfile
import unittest
from pathlib import Path

from aki_agent.orchestrator import Orchestrator
from aki_agent.planning import HeuristicPlanner
from aki_agent.policy import PolicyGateway
from aki_agent.tools import ArtifactStore, ToolRegistry
from aki_agent.types import ToolCall


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.registry = ToolRegistry(self.root, PolicyGateway(self.root), ArtifactStore(self.root / ".aki" / "artifacts"))

    def tearDown(self):
        self.directory.cleanup()

    def test_blocks_path_escape(self):
        result = self.registry.invoke(ToolCall("read_file", {"path": "../outside.txt"}))
        self.assertFalse(result.ok)
        self.assertIn("escapes", result.error)

    def test_blocks_write_without_confirmation(self):
        result = self.registry.invoke(ToolCall("write_file", {"path": "x.txt", "content": "no"}))
        self.assertFalse(result.ok)
        self.assertIn("approve", result.error)

    def test_blocks_shell_chaining(self):
        result = self.registry.invoke(ToolCall("run_command", {"command": "pytest; echo unsafe"}))
        self.assertFalse(result.ok)

    def test_blocks_command_that_only_looks_like_allowlisted_command(self):
        result = self.registry.invoke(ToolCall("run_command", {"command": "pytest-malicious"}))
        self.assertFalse(result.ok)

    def test_blocks_tool_outside_skill_scope(self):
        result = self.registry.invoke(ToolCall("write_file", {"path": "x.txt", "content": "no"}), {"read_file"})
        self.assertFalse(result.ok)
        self.assertIn("skill scope", result.error)

    def test_allows_scoped_write_when_approved(self):
        registry = ToolRegistry(self.root, PolicyGateway(self.root, approve_writes=True), ArtifactStore(self.root / ".aki" / "artifacts"))
        result = registry.invoke(ToolCall("write_file", {"path": "nested/x.txt", "content": "ok"}))
        self.assertTrue(result.ok)
        self.assertEqual((self.root / "nested/x.txt").read_text(), "ok")


class OrchestrationTests(unittest.TestCase):
    def test_routes_and_runs_read_only_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "example.py").write_text("# TODO: make this better\n")
            state = Orchestrator(root).run("搜索 TODO")
            self.assertTrue(state.selected_skills)
            self.assertTrue(any(result.worker == "research" for result in state.results))
            self.assertTrue((root / ".aki" / "memory.jsonl").exists())
            self.assertIsNotNone(state.plan)
            self.assertEqual(state.plan.steps[0].status, "success")

    def test_model_tool_calls_are_traced_and_skill_scoped(self):
        with tempfile.TemporaryDirectory() as directory:
            agent = Orchestrator(Path(directory))
            state = agent.run("搜索 TODO")
            result = agent.execute_tool_calls(state, [ToolCall("write_file", {"path": "x.txt", "content": "no"})])[0]
            self.assertFalse(result.ok)
            self.assertEqual(len(state.tool_trace), 1)

    def test_reuses_memory_and_builds_context_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "example.py").write_text("# TODO: make this better\n")
            agent = Orchestrator(root)
            agent.run("搜索 TODO")
            state = agent.run("搜索 TODO")
            context = agent.build_context(state).render()
            self.assertEqual(len(state.recalled_memory), 1)
            self.assertIn("运行约束", context)
            self.assertIn("可复用记忆", context)

    def test_implementation_plan_has_ordered_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            agent = Orchestrator(Path(directory))
            skills = agent.router.route("实现一个功能", "implement")
            plan = HeuristicPlanner().build("实现一个功能", "implement", skills)
            self.assertEqual([step.worker for step in plan.steps], ["research", "code", "test"])
            self.assertEqual(plan.steps[1].depends_on, [plan.steps[0].step_id])
