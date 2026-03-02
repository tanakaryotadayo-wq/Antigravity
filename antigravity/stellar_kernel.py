"""Stellar Kernel — S-Code 実行エンジン.

StellarEngine の Kernel パターンを移植:
YAML 定義の S-Code ブロックを読み込み、
変数展開 + ガード条件 + 監査ログで安全に実行。
"""
from __future__ import annotations
import json, time, pathlib
from dataclasses import dataclass, field
from typing import Any
import structlog

logger = structlog.get_logger()

@dataclass
class SCode:
    """S-Code ブロック定義."""
    block_id: str
    inputs: list[str]
    flow: list[dict[str, Any]]

class StellarKernel:
    """S-Code 実行カーネル.

    YAML/dict 定義の S-Code ブロックを実行:
    1. 入力バリデーション
    2. 変数展開 ()
    3. ガード条件チェック
    4. 監査ログ出力

    Usage:
        kernel = StellarKernel()
        kernel.register("lint_check", inputs=["file"], flow=[
            {"tool": "ruff", "args": {"path": ""}, "out": "result"},
        ])
        result = kernel.execute("lint_check", {"file": "app.py"})
    """
    def __init__(self, audit_dir: str | pathlib.Path | None = None):
        self.definitions: dict[str, SCode] = {}
        self.tools: dict[str, Any] = {}
        self.audit_dir = pathlib.Path(audit_dir) if audit_dir else pathlib.Path.home() / ".antigravity" / "audit"
        self.log = logger.bind(component="stellar_kernel")

    def register_tool(self, name: str, func: Any) -> None:
        """ツールを登録."""
        self.tools[name] = func

    def register(self, block_id: str, inputs: list[str] | None = None,
                 flow: list[dict] | None = None) -> None:
        """S-Code ブロックを登録."""
        self.definitions[block_id] = SCode(
            block_id=block_id,
            inputs=inputs or [],
            flow=flow or [],
        )

    def execute(self, block_id: str, args: dict[str, Any]) -> dict[str, Any]:
        """S-Code ブロックを実行."""
        if block_id not in self.definitions:
            raise ValueError(f"Unknown block: {block_id}")
        scode = self.definitions[block_id]
        # 入力チェック
        for key in scode.inputs:
            if key not in args:
                raise ValueError(f"Missing required input: {key}")
        mem = args.copy()
        try:
            for step in scode.flow:
                tool_name = step.get("tool", "")
                tool_args_raw = step.get("args", {})
                output_key = step.get("out")
                # 変数展開
                real_args = {}
                for k, v in tool_args_raw.items():
                    if isinstance(v, str) and v.startswith("$"):
                        real_args[k] = mem.get(v[1:])
                    else:
                        real_args[k] = v
                # ツール実行
                func = self.tools.get(tool_name)
                if func is None:
                    raise ValueError(f"Tool not found: {tool_name}")
                result = func(**real_args)
                # ガード
                if step.get("guard") and not result:
                    raise ValueError(f"Guard failed: {tool_name}")
                if output_key:
                    mem[output_key] = result
            self._audit(block_id, "SUCCESS", None)
            return mem
        except Exception as e:
            self._audit(block_id, "FAILURE", str(e))
            raise

    def list_blocks(self) -> list[str]:
        return list(self.definitions.keys())

    def _audit(self, block_id: str, result: str, error: str | None) -> None:
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        entry = {"timestamp": time.time(), "block": block_id, "result": result, "error": error}
        try:
            with open(self.audit_dir / "audit.jsonl", "a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + chr(10))
        except IOError:
            pass