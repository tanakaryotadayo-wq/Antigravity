"""Codex CLI ラッパー."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import structlog

from antigravity.gate_engine import GateEngine

logger = structlog.get_logger()


def run(prompt: str, *, engine: GateEngine, project_dir: str = ".") -> int:
    """Codex CLI をゲート付きで実行."""
    project = Path(project_dir).resolve()
    codex_cmd = _find_codex()
    if not codex_cmd:
        print("codex コマンドが見つかりません", file=sys.stderr)
        return 1
    logger.info("launching_codex", prompt=prompt[:50])
    env = os.environ.copy()
    env["FUSION_GATE_V4"] = "active"
    try:
        result = subprocess.run([codex_cmd, "-p", prompt], cwd=project, env=env)
        return result.returncode
    except KeyboardInterrupt:
        return 130


def _find_codex() -> str | None:
    import shutil
    return shutil.which("codex")
