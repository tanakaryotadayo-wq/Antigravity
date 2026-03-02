"""Stellar Cortex — 自律推論・実行ループ.

StellarEngine の StellarCortex パターンを移植:
plan() -> execute_step() -> solve() の自律ループ。
Gate Engine と統合して安全な自律実行を提供。
"""
from __future__ import annotations
import json, time
from dataclasses import dataclass, field
from typing import Any
import structlog
from antigravity.gate_engine import GateEngine, Decision

logger = structlog.get_logger()

TOOL_MAP: dict[str, str] = {
    "GATE.check_prompt": "gate.check_prompt",
    "GATE.check_command": "gate.check_command",
    "GATE.check_write": "gate.check_write",
    "GATE.quality_gate": "gate.quality_gate",
    "TERMINAL.run": "terminal.run",
    "FS.read": "filesystem.read",
    "FS.write": "filesystem.write",
    "FS.search": "filesystem.search",
    "CORTEX.reason": "_internal_reason",
}

@dataclass
class Step:
    step_id: int
    action: str
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    status: str = "pending"

@dataclass
class CortexMemory:
    goal: str
    steps: list[Step] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)

class StellarCortex:
    """自律推論・実行エンジン.

    StellarEngine のコアパターンを Antigravity に統合:
    1. plan() — ゴールからステップを生成
    2. execute_step() — Gate Engine で検問しながら実行
    3. solve() — 自律ループで完了まで実行

    Usage:
        cortex = StellarCortex()
        result = cortex.solve("プロジェクトのリント問題を修正")
    """
    def __init__(self, gate_engine: GateEngine | None = None):
        self.gate = gate_engine or GateEngine()
        self.log = logger.bind(component="stellar_cortex")
        self.memory: list[CortexMemory] = []

    def plan(self, goal: str, steps: list[dict] | None = None) -> CortexMemory:
        """ゴールから実行プランを生成."""
        self.log.info("planning", goal=goal)
        mem = CortexMemory(goal=goal)
        if steps:
            for i, s in enumerate(steps):
                mem.steps.append(Step(
                    step_id=i + 1,
                    action=s.get("action", ""),
                    tool=s.get("tool", "CORTEX.reason"),
                    args=s.get("args", {}),
                ))
        self.memory.append(mem)
        return mem

    def execute_step(self, step: Step, mem: CortexMemory) -> Any:
        """Gate Engine で検問しながらステップ実行."""
        self.log.info("executing", step_id=step.step_id, action=step.action, tool=step.tool)
        # Gate 検問
        if step.tool.startswith("TERMINAL"):
            cmd = step.args.get("command", "")
            gate_result = self.gate.check_command(cmd)
            if gate_result.decision == Decision.BLOCK:
                step.status = "blocked"
                step.result = f"BLOCKED: {gate_result.reason}"
                return step.result
        if step.tool == "CORTEX.reason":
            step.result = f"Reasoned: {step.args.get("thought", step.action)}"
            step.status = "done"
            return step.result
        # ツール実行（実際の実行は外部から注入）
        step.result = {"tool": step.tool, "args": step.args, "status": "dispatched"}
        step.status = "done"
        mem.context[f"step_{step.step_id}"] = step.result
        return step.result

    def solve(self, goal: str, steps: list[dict] | None = None) -> CortexMemory:
        """自律ループでゴール達成."""
        self.log.info("solving", goal=goal)
        mem = self.plan(goal, steps)
        for step in mem.steps:
            self.execute_step(step, mem)
            if step.status == "blocked":
                self.log.warning("step_blocked", step_id=step.step_id)
        return mem

    def get_history(self) -> list[dict]:
        """実行履歴."""
        return [
            {"goal": m.goal, "steps": len(m.steps),
             "completed": sum(1 for s in m.steps if s.status == "done"),
             "blocked": sum(1 for s in m.steps if s.status == "blocked")}
            for m in self.memory
        ]