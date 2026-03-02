"""Stellar Engine パターン統合テスト."""
from antigravity.cortex import StellarCortex, Step
from antigravity.stellar_kernel import StellarKernel
from antigravity.eidolon import EidolonReflector


class TestStellarCortex:
    def setup_method(self):
        self.cortex = StellarCortex()

    def test_plan(self):
        mem = self.cortex.plan("test goal", [
            {"action": "reason about goal", "tool": "CORTEX.reason", "args": {"thought": "thinking..."}},
        ])
        assert mem.goal == "test goal"
        assert len(mem.steps) == 1

    def test_solve_reason(self):
        mem = self.cortex.solve("simple task", [
            {"action": "think", "tool": "CORTEX.reason", "args": {"thought": "ok"}},
        ])
        assert mem.steps[0].status == "done"
        assert "Reasoned" in mem.steps[0].result

    def test_solve_blocked(self):
        mem = self.cortex.solve("dangerous task", [
            {"action": "delete everything", "tool": "TERMINAL.run", "args": {"command": "rm -rf /"}},
        ])
        assert mem.steps[0].status == "blocked"

    def test_history(self):
        self.cortex.solve("g1", [{"action": "a", "tool": "CORTEX.reason"}])
        self.cortex.solve("g2", [{"action": "b", "tool": "CORTEX.reason"}])
        history = self.cortex.get_history()
        assert len(history) == 2


class TestStellarKernel:
    def setup_method(self):
        self.kernel = StellarKernel(audit_dir="/tmp/antigravity_test_audit")
        self.kernel.register_tool("echo", lambda msg: f"echoed: {msg}")

    def test_register_and_execute(self):
        self.kernel.register("greet", inputs=["name"], flow=[
            {"tool": "echo", "args": {"msg": "$name"}, "out": "result"},
        ])
        mem = self.kernel.execute("greet", {"name": "Ryota"})
        assert mem["result"] == "echoed: Ryota"

    def test_missing_input(self):
        self.kernel.register("need_input", inputs=["x"])
        try:
            self.kernel.execute("need_input", {})
            assert False, "Should have raised"
        except ValueError as e:
            assert "Missing" in str(e)

    def test_unknown_block(self):
        try:
            self.kernel.execute("nope", {})
            assert False
        except ValueError as e:
            assert "Unknown" in str(e)

    def test_guard_fail(self):
        self.kernel.register_tool("falsy", lambda: None)
        self.kernel.register("guarded", flow=[
            {"tool": "falsy", "guard": True, "out": "r"},
        ])
        try:
            self.kernel.execute("guarded", {})
            assert False
        except ValueError as e:
            assert "Guard" in str(e)

    def test_list_blocks(self):
        self.kernel.register("b1")
        self.kernel.register("b2")
        assert "b1" in self.kernel.list_blocks()
        assert "b2" in self.kernel.list_blocks()


class TestEidolonReflector:
    def setup_method(self):
        self.eidolon = EidolonReflector(data_dir="/tmp/antigravity_test_eidolon")

    def test_reflect_normal(self):
        q = self.eidolon.reflect({"query": "hello"})
        assert isinstance(q, str) and len(q) > 0

    def test_reflect_blocked(self):
        q = self.eidolon.reflect({"query": "x", "blocked_steps": [1, 2]})
        assert "ブロック" in q

    def test_absorb(self):
        axiom = self.eidolon.absorb("q1", "what?", "use async patterns")
        assert axiom.keywords
        assert "async" in axiom.keywords or "patterns" in axiom.keywords

    def test_get_axioms(self):
        self.eidolon.absorb("q1", "q?", "answer one")
        self.eidolon.absorb("q2", "q?", "answer two")
        axioms = self.eidolon.get_axioms()
        assert len(axioms) >= 2
