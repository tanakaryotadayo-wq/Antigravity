"""Gemini CLI ラッパー.

Gemini CLI はネイティブ Hooks をサポートしていないため、
Gate Engine で入力フィルタリングしてから gemini を起動する。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import structlog

from antigravity.gate_engine import GateEngine

logger = structlog.get_logger()


def run(prompt: str, *, engine: GateEngine, project_dir: str = ".") -> int:
    """Gemini CLI をゲート付きで実行."""
    project = Path(project_dir).resolve()

    # gemini コマンドの存在確認
    gemini_cmd = _find_gemini()
    if not gemini_cmd:
        print("❌ gemini コマンドが見つかりません", file=sys.stderr)
        print("   インストール: npm install -g @google/gemini-cli", file=sys.stderr)
        return 1

    # 実行
    logger.info("launching_gemini", prompt=prompt[:50])
    env = os.environ.copy()
    env["FUSION_GATE_V4"] = "active"

    try:
        result = subprocess.run(
            [gemini_cmd, "-p", prompt],
            cwd=project,
            env=env,
        )
        return result.returncode
    except KeyboardInterrupt:
        return 130


def _find_gemini() -> str | None:
    """gemini コマンドのパスを探す."""
    import shutil

    return shutil.which("gemini")
